import json
import os
import pathlib
import re
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from django.core import serializers
from django.db.models import Count
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.query import Query
from toolkit.embedding.models import Embedding
from toolkit.torchtagger.models import TorchTagger
from toolkit.serializer_constants import (FeedbackSerializer, ProjectResourceBulkDeleteSerializer, ProjectResourceImportModelSerializer)
from toolkit.settings import BASE_DIR
from toolkit.tagger.models import Tagger
from toolkit.tools.logger import Logger


class TagLogicViews:
    """Re-usable logic for when a view needs to deal with facts"""


    def get_tags(self, fact_name, active_project, min_count=1000, max_count=None):
        """Finds possible tags for training by aggregating active project's indices."""
        active_indices = list(active_project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values


    def create_queries(self, fact_name, tags):
        """Creates queries for finding documents for each tag."""
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            queries.append(query.query)
        return queries


class BulkDelete:
    @action(detail=False, methods=['post'], serializer_class=ProjectResourceBulkDeleteSerializer)
    def bulk_delete(self, request, project_pk=None):
        """Deletes bulk of objects, given { "ids": [int] }"""
        data = request.data
        if "ids" not in data:
            return Response({'error': 'Must include key "ids" with an array of integers (private keys)'}, status=status.HTTP_400_BAD_REQUEST)
        deleted = self.get_queryset().filter(id__in=data['ids'], project_id=project_pk).delete()
        # Show  the number of objects deleted and a dictionary with the number of deletions per object type
        info = {"num_deleted": deleted[0], "deleted_types": deleted[1]}
        return Response(info, status=status.HTTP_200_OK)


class ExportModel:
    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Exports and saves any model object as zip file."""

        model_object = self.get_object()  # retrieve model object

        # check if model completed
        if model_object.task.status != model_object.task.STATUS_COMPLETED:
            return Response({'error': 'model is not completed'}, status=status.HTTP_400_BAD_REQUEST)

        # declare file names for the model
        zip_name = f'model_{model_object.pk}.zip'
        json_name = f'model_{model_object.pk}.json'

        with SpooledTemporaryFile() as tmp:
            with ZipFile(tmp, 'w', ZIP_DEFLATED) as archive:
                # write model object to zip as json
                model_json = serializers.serialize('json', [model_object])
                archive.writestr(json_name, model_json)
                model_json_loaded = json.loads(model_json)[0]
                # write model files to zip
                model_type = model_json_loaded['model'].split('.')[-1]
                # if model is embedding
                if model_type == "embedding":
                    embedding_path = model_object.embedding_model.path
                    phraser_path = model_object.phraser_model.path
                    for model_path in (embedding_path, phraser_path):
                        # derive model type from model name
                        new_model_path = os.path.join('data', 'models', model_type, os.path.basename(model_path))
                        archive.write(model_path, arcname=new_model_path)
                # if model is torchtagger
                elif model_type == "torchtagger":
                    model_path = model_object.model.path
                    text_field_path = model_object.text_field.path
                    for path in (model_path, text_field_path):
                        # derive model type from model name
                        new_model_path = os.path.join('data', 'models', model_type, os.path.basename(path))
                        archive.write(path, arcname=new_model_path)
                # write plot files to zip. we need to check, because e.g. embeddings do not have plots (yet?)
                if hasattr(model_object, 'plot'):
                    plot_path = model_object.plot.path
                    new_plot_path = os.path.join('data', 'media', os.path.basename(plot_path))
                    archive.write(plot_path, arcname=new_plot_path)
            # reset file pointer
            tmp.seek(0)
            # write file data to response
            response = HttpResponse(tmp.read())
            # download file
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
            return response


class ImportModel:
    @action(detail=True, methods=['post'], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None):
        """Imports any saved model object (tagger, embedding, torchtagger, etc.) from zip file."""
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # retrieve file
        uploaded_file = serializer.validated_data['file']
        try:
            with ZipFile(uploaded_file, 'r') as archive:
                zip_content = archive.namelist()
                if not self.validate_zip(zip_content):
                    Response({'error': 'zip file content does not meet current standard'}, status=status.HTTP_400_BAD_REQUEST)

                json_file = [f for f in zip_content if f.endswith('.json')]
                model_json = json.loads(archive.read(json_file[0]).decode())[0]
                # remove object pk to avoid id clash (django will create one)
                del model_json['pk']
                # remove task object and let django create new
                del model_json['fields']['task']
                # update object project & user to match current
                model_json['fields']['project'] = pk
                model_json['fields']['author'] = request.user.id
                # deserialize json into django object
                model_object = list(serializers.deserialize('json', json.dumps([model_json])))[0]
                model_object = model_object.object
                model_object.save()
                # save model files to disk
                self.save_files(archive, zip_content, model_object)
                # update task to completed and save again

                model_object = self._create_fitting_task(model_object)
                model_object.task.save()
                model_object.save()

                success_response = {'id': model_object.id, 'model': model_json['model']}
            return Response(success_response, status=status.HTTP_200_OK)

        except Exception as e:
            Logger().error('error importing model', exc_info=e)
            return Response({'error': f'error importing model: {e}'}, status=status.HTTP_400_BAD_REQUEST)


    def _create_fitting_task(self, model_object):
        if isinstance(model_object, TorchTagger):
            model_object.task = Task.objects.create(torchtagger=model_object, status='created')
            model_object.task.status = model_object.task.STATUS_COMPLETED
            return model_object

        elif isinstance(model_object, Embedding):
            if isinstance(model_object, Embedding):
                model_object.task = Task.objects.create(embedding=model_object, status='created')
                model_object.task.status = model_object.task.STATUS_COMPLETED
                return model_object

        elif isinstance(model_object, Tagger):
            if isinstance(model_object, Tagger):
                model_object.task = Task.objects.create(tagger=model_object, status='created')
                model_object.task.status = model_object.task.STATUS_COMPLETED
                return model_object


    @staticmethod
    def validate_zip(zip_content):
        # check if model json inside zip
        if not [f for f in zip_content if f.endswith('.json')]:
            return False
        # check if model files present
        if not [f for f in zip_content if f.startswith('data/models')]:
            return False
        return True


    def save_files(self, archive, zip_content, model_object):
        # identify relevant files
        plot_files = [f for f in zip_content if f.startswith('data/media') and f.endswith('.png')]
        model_files = [f for f in zip_content if f.startswith('data/models')]
        # write plot file (if any) to disk
        for plot_file in plot_files:
            with open(os.path.join(BASE_DIR, plot_file), 'wb') as fh:
                fh.write(archive.read(plot_file))
        # write model files to disk
        # update model path in model object
        if isinstance(model_object, TorchTagger):
            for path in model_files:
                if path in model_object.model.path:
                    new_path = self._generate_fitting_name(model_object, path)
                    with open(os.path.join(BASE_DIR, new_path), 'wb') as fh:
                        fh.write(archive.read(path))
                    model_object.model = new_path

                elif path in model_object.text_field.path:
                    new_path = self._generate_fitting_name(model_object, path)
                    with open(os.path.join(BASE_DIR, new_path), 'wb') as fh:
                        fh.write(archive.read(path))
                    model_object.text_field = new_path

        elif isinstance(model_object, Embedding):
            for path in model_files:
                if path in model_object.embedding_model.path:
                    new_path = self._generate_fitting_name(model_object, path)
                    with open(os.path.join(BASE_DIR, new_path), 'wb') as fh:
                        fh.write(archive.read(path))
                    model_object.embedding_model = new_path

                elif path in model_object.phraser_model.path:
                    new_path = self._generate_fitting_name(model_object, path)
                    with open(os.path.join(BASE_DIR, new_path), 'wb') as fh:
                        fh.write(archive.read(path))
                    model_object.phraser_model = new_path

        elif isinstance(model_object, Tagger):
            for path in model_files:
                if path in model_object.model.path:
                    new_path = self._generate_fitting_name(model_object, path)
                    with open(os.path.join(BASE_DIR, new_path), 'wb') as fh:
                        fh.write(archive.read(path))
                    model_object.model = new_path


    def _generate_fitting_name(self, model_object, filename):
        """
        Generates a new file name to avoid duplicates.
        :param model_object: Instance of a Django model like TorchTagger or Embedding.
        :param filename: Path of the model from the root directory: ex data/models/torchtagger/torchtagger_1_hash
        :return: New file name for the model file.
        """
        path = pathlib.Path(filename)
        file = str(pathlib.Path(path.stem + path.suffix))

        if isinstance(model_object, TorchTagger):
            if "torchtagger" in file and "text_field" in file:
                new_path = pathlib.Path(path.parent, model_object.generate_name("torchtagger") + path.suffix + "_text_field")
                return str(new_path)
            elif "torchtagger" in file:
                new_path = pathlib.Path(path.parent, model_object.generate_name("torchtagger") + path.suffix)
                return str(new_path)

        elif isinstance(model_object, Embedding):
            if "embedding" in file:
                new_path = pathlib.Path(path.parent, model_object.generate_name("embedding") + path.suffix)
                return str(new_path)
            elif "phraser" in file:
                new_path = pathlib.Path(path.parent, model_object.generate_name("phraser") + path.suffix)
                return str(new_path)

        elif isinstance(model_object, Tagger):
            pass


    @staticmethod
    def rewrite_model_id(_id, model_path):
        """Rewrites id in model name"""
        model_basename = os.path.basename(model_path)
        model_basename = re.sub('_(\d)+_', f'_{_id}_', model_basename)
        model_dir = os.path.dirname(model_path)
        return os.path.join(model_dir, model_basename)


class FeedbackModelView:
    @action(detail=True, methods=['get', 'post', 'delete'], serializer_class=FeedbackSerializer)
    def feedback(self, request, project_pk=None, pk=None):
        """
        get:
        Retrieves feedback for the model.

        post:
        Adds feedback to the model.

        delete:
        Deletes feedback object for the model.
        """
        model_object = self.get_object()
        feedback = Feedback(project_pk, model_object=model_object)
        if request.method == 'POST':
            serializer = FeedbackSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            added = feedback.add(serializer.validated_data['feedback_id'], serializer.validated_data['correct_prediction'])
            return Response(added, status=status.HTTP_200_OK)
        elif request.method == 'DELETE':
            feedback_deleted = feedback.delete()
            return Response(feedback_deleted, status=status.HTTP_200_OK)
        elif request.method == 'GET':
            feedback_list = feedback.list()
            return Response(feedback_list, status=status.HTTP_200_OK)


class FeedbackIndexView:
    @action(detail=True, methods=['get', 'delete'])
    def feedback(self, request, pk=None):
        """
        get:
        Retrieves content for feedback index for the project

        delete:
        Deletes feedback index for the project.
        """
        feedback = Feedback(pk)
        if request.method == 'DELETE':
            feedback_deleted = feedback.delete_index()
            return Response(feedback_deleted, status=status.HTTP_200_OK)
        elif request.method == 'GET':
            feedback_list = feedback.list()
            return Response(feedback_list, status=status.HTTP_200_OK)


class AdminPermissionsViewSetMixin(object):
    ''' When admin and/or project_owners need a different serialization '''


    def get_serializer_class(self):
        current_user = self.request.user
        if current_user.is_superuser:
            return ProjectAdminSerializer
        else:
            return super(AdminPermissionsViewSetMixin, self).get_serializer_class()
