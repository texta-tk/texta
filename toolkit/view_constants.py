from tempfile import SpooledTemporaryFile
from zipfile import ZipFile, ZIP_DEFLATED
import json
import os
import re

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from django.core import serializers
from django.http import HttpResponse

from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query
from toolkit.serializer_constants import ProjectResourceBulkDeleteSerializer, ProjectResourceImportModelSerializer
from toolkit.settings import BASE_DIR
from toolkit.tools.logger import Logger

class TagLogicViews():
    '''Re-usable logic for when a view needs to deal with facts'''

    def get_tags(self, fact_name, active_project, min_count=1000, max_count=None):
        """
        Finds possible tags for training by aggregating active project's indices.
        """
        active_indices = list(active_project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values

    def create_queries(self, fact_name, tags):
        """
        Creates queries for finding documents for each tag.
        """
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            queries.append(query.query)
        return queries


class BulkDelete():
    @action(detail=False, methods=['post'], serializer_class=ProjectResourceBulkDeleteSerializer)
    def bulk_delete(self, request, project_pk=None):
        '''API endpoint for bulk deleting objects, given { "ids": [int] }'''
        data = request.data
        if not "ids" in data:
            return Response({'error': 'Must include key "ids" with an array of integers (private keys)'}, status=status.HTTP_400_BAD_REQUEST)
        deleted = self.get_queryset().filter(id__in=data['ids'], project_id=project_pk).delete()
        # Show  the number of objects deleted and a dictionary with the number of deletions per object type
        info = {"num_deleted": deleted[0], "deleted_types": deleted[1] }
        return Response(info, status=status.HTTP_200_OK)


class ExportModel():
    @action(detail=True, methods=['get'])
    def export_tagger(self, request, pk=None, project_pk=None):
        '''API endpoint for exporting the model.'''
        # retrieve model object
        model_object = self.get_object()
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
                # write model files to zip
                for model_type, model_path in json.loads(model_object.location).items():
                    new_model_path = os.path.join('data', 'models', model_type, os.path.basename(model_path))
                    archive.write(model_path, arcname=new_model_path)
                # write plot files to zip
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
        return Response()


class ImportModel():
    @action(detail=False, methods=['post'], serializer_class=ProjectResourceImportModelSerializer)
    def import_tagger(self, request, project_pk=None):
        '''API endpoint for importing the model.'''
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
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
                # remove embedding THIS IS A HACK!
                del model_json['fields']['embedding']
                # remove task object and let django create new
                del model_json['fields']['task']
                # update object project & user to match current
                model_json['fields']['project'] = project_pk
                model_json['fields']['author'] = request.user.id
                # deserialize json into django object
                model_object = list(serializers.deserialize('json', json.dumps([model_json])))[0]
                model_object = model_object.object
                # save object
                model_object.save()
                # save model files to disk
                model_object = self.save_files(archive, zip_content, model_object)
            # update task to completed and save again
            model_object.task.status = model_object.task.STATUS_COMPLETED
            model_object.save()
            success_response = {'imported': [{'id': model_object.id, 'model': model_json['model']}]}
            return Response(success_response, status=status.HTTP_200_OK)
        except Exception as e:
            Logger().error('error importing model', exc_info=e)
            return Response({'error': f'error importing model: {e}'}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def validate_zip(zip_content):
        # check if model json inside zip
        if not [f for f in zip_content if f.endswith('.json')]:
            return False
        # check if plot present
        if not [f for f in zip_content if f.startswith('data/media') and f.endswith('.png')]:
            return False
        # check if model files present
        if not [f for f in zip_content if f.startswith('data/models')]:
            return False
        return True

    def save_files(self, archive, zip_content, model_object):
        # identify relevant files
        plot_file = [f for f in zip_content if f.startswith('data/media') and f.endswith('.png')][0]
        model_files = [f for f in zip_content if f.startswith('data/models')]
        # write plot file to disk
        with open(os.path.join(BASE_DIR, plot_file), 'wb') as fh:
            fh.write(archive.read(plot_file))
        # write model files to disk
        for model_file in model_files:
            new_model_file = self.rewrite_model_id(model_object.id, model_file)
            with open(os.path.join(BASE_DIR, new_model_file), 'wb') as fh:
                fh.write(archive.read(model_file))
            # update model path in model object
            new_location = {k: self.rewrite_model_id(model_object.id, v) for k, v in json.loads(model_object.location).items()}
            model_object.location = json.dumps(new_location)
        return model_object
    
    @staticmethod
    def rewrite_model_id(_id, model_path):
        '''Rewrites id in model name'''
        model_basename = os.path.basename(model_path)
        model_basename = re.sub('_(\d)+_', f'_{_id}_', model_basename)
        model_dir = os.path.dirname(model_path)
        return os.path.join(model_dir, model_basename)
