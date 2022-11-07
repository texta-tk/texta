import json
import logging
import os
from shutil import rmtree

import rest_framework.filters as drf_filters
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.utils._os import safe_join
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher

from toolkit.bert_tagger import choices
from toolkit.bert_tagger.models import BertTagger as BertTaggerObject
from toolkit.bert_tagger.serializers import (ApplyTaggerSerializer, BertDownloaderSerializer, BertTagTextSerializer, BertTaggerSerializer, DeleteBERTModelSerializer,
                                             EpochReportSerializer, TagRandomDocSerializer)
from toolkit.bert_tagger.tasks import apply_tagger, apply_tagger_to_index, download_tagger_model, upload_tagger_files
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.exceptions import DownloadingModelsNotAllowedError, InvalidModelIdentifierError, NonExistantModelError, ProjectValidationFailed
from toolkit.helper_functions import add_finite_url_to_feedback, download_bert_requirements, get_downloaded_bert_models, minio_connection
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer, S3UploadSerializer, S3DownloadSerializer
from toolkit.view_constants import BulkDelete, FavoriteModelViewMixing, FeedbackModelView
from .tasks import apply_persistent_bert_tagger
from ..filter_constants import FavoriteFilter


class BertTaggerFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('tasks__status', lookup_expr='icontains')

    class Meta:
        model = BertTaggerObject
        fields = []


class BertTaggerViewSet(viewsets.ModelViewSet, BulkDelete, FeedbackModelView, FavoriteModelViewMixing):
    serializer_class = BertTaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectAccessInApplicationsAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = BertTaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score', 'precision', 'recall', 'tasks__status')

    def perform_create(self, serializer, **kwargs):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")

        serializer_query = serializer.validated_data.get("query")

        if isinstance(serializer_query, str):
            # If query is passed as JSON string to the serializer
            query = serializer_query
        else:
            # If query is passed as raw JSON to the serializer
            query = json.dumps(serializer_query)

        tagger: BertTaggerObject = serializer.save(
            author=self.request.user,
            project=project,
            query=query,
            fields=json.dumps(serializer.validated_data['fields']),
            **kwargs
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            tagger.indices.add(index)

        tagger.train()

    def get_queryset(self):
        return BertTaggerObject.objects.filter(project=self.kwargs['project_pk']).order_by('-id')

    @action(detail=True, methods=['post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the BertTagger model."""
        instance = self.get_object()
        instance.train()
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Returns list of tags for input text."""
        zip_name = f'berttagger_model_{pk}.zip'

        tagger_object: BertTaggerObject = self.get_object()
        data = tagger_object.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response

    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        tagger_id = BertTaggerObject.import_resources(uploaded_file, request.user.pk, project_pk)
        return Response({"id": tagger_id, "message": "Successfully imported model and associated files."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], serializer_class=TagRandomDocSerializer)
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""

        # get tagger object
        tagger_object: BertTaggerObject = self.get_object()

        # check if tagger exists
        if not tagger_object.model:
            raise NonExistantModelError()

        serializer = TagRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = tagger_object.get_available_or_all_indices(indices)

        # retrieve tagger fields
        # if user specified fields, use them
        if serializer.validated_data["fields"]:
            tagger_fields = serializer.validated_data["fields"]
        else:
            tagger_fields = json.loads(tagger_object.fields)

        if not ElasticCore().check_if_indices_exist(indices):
            raise ProjectValidationFailed(detail=f'One or more index from {list(indices)} do not exist')

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]

        # filter out correct fields from the document
        random_doc_filtered = {k: v for k, v in random_doc.items() if k in tagger_fields}

        # apply tagger
        tagger_response = apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=BertTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = BertTagTextSerializer(data=request.data)
        # check if valid request
        serializer.is_valid(raise_exception=True)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.model:
            raise NonExistantModelError()
        # apply tagger
        text = serializer.validated_data['text']
        feedback = serializer.validated_data['feedback_enabled']
        persistent = serializer.validated_data['persistent']
        # decide whether to store the model in cache
        if not persistent:
            prediction = apply_tagger(tagger_object, text, feedback=feedback)
        else:
            prediction = apply_persistent_bert_tagger.s(text, tagger_object.pk, feedback=feedback).apply_async().get()
        prediction = add_finite_url_to_feedback(prediction, request)
        return Response(prediction, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post', 'get'], serializer_class=EpochReportSerializer)
    def epoch_reports(self, request, pk=None, project_pk=None):
        """Retrieve epoch reports"""
        tagger_object: BertTaggerObject = self.get_object()

        if request.method == "GET":
            ignore_fields = choices.DEFAULT_REPORT_IGNORE_FIELDS
        else:
            serializer = EpochReportSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            ignore_fields = serializer.validated_data['ignore_fields']

        reports = json.loads(tagger_object.epoch_reports)
        filtered_reports = [{field: value for field, value in list(report.items()) if field not in ignore_fields} for report in reports]

        return Response(filtered_reports, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], serializer_class=BertDownloaderSerializer, permission_classes=(IsAdminUser,))
    def download_pretrained_model(self, request, pk=None, project_pk=None):
        """Download pretrained BERT models."""

        serializer = BertDownloaderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bert_model = serializer.validated_data['bert_model']
        if settings.ALLOW_BERT_MODEL_DOWNLOADS:
            errors, failed_models = download_bert_requirements(
                settings.BERT_PRETRAINED_MODEL_DIRECTORY,
                [bert_model],
                cache_directory=settings.BERT_CACHE_DIR,
                logger=logging.getLogger(settings.INFO_LOGGER)
            )

            if failed_models:
                error_msgs = []
                for i, model in enumerate(failed_models):
                    msg = f"Failed downloading model: {failed_models[i]}. Reason: {type(errors[i])}: {str(errors[i])}"
                    error_msgs.append(msg)
                error_msg = "\n".join(error_msgs)
                raise InvalidModelIdentifierError(error_msg)
        else:
            raise DownloadingModelsNotAllowedError()
        return Response("Download finished.", status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=S3UploadSerializer)
    @minio_connection
    def upload_into_s3(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minio_path = serializer.validated_data["minio_path"]
        tagger = self.get_object()
        task = Task.objects.create(berttagger=tagger, status=Task.STATUS_QUEUED, task_type=Task.TYPE_UPLOAD)
        tagger.tasks.add(task)
        transaction.on_commit(lambda: upload_tagger_files.apply_async(args=(tagger.pk, minio_path), queue=settings.CELERY_LONG_TERM_TASK_QUEUE))
        return Response({"message": "Started task for uploading model into S3!"})

    @action(detail=False, methods=['post'], serializer_class=S3DownloadSerializer)
    @minio_connection
    def download_from_s3(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minio_path = serializer.validated_data["minio_path"]
        version_id = serializer.validated_data["version_id"]

        transaction.on_commit(lambda: download_tagger_model.apply_async(args=(minio_path, request.user.pk, project_pk, version_id), queue=settings.CELERY_LONG_TERM_TASK_QUEUE))

        return Response({"message": "Started task for downloading model from S3!"})

    @action(detail=False, methods=['get'])
    def available_models(self, request, pk=None, project_pk=None):
        """Retrieve downloaded BERT models."""
        available_models = get_downloaded_bert_models(settings.BERT_PRETRAINED_MODEL_DIRECTORY)

        return Response(available_models, status=status.HTTP_200_OK)

    # This is made into a POST request instead of DELETE, so it would be nice to use through the Browsable API.
    @action(detail=False, methods=['post'], serializer_class=DeleteBERTModelSerializer, permission_classes=(IsAdminUser,))
    def delete_pretrained_model(self, request, pk=None, project_pk=None):
        """Delete existing BERT models."""
        serializer: DeleteBERTModelSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        model_name = serializer.validated_data["model_name"]

        from texta_bert_tagger.tagger import BertTagger
        file_name = BertTagger.normalize_name(model_name)
        path = safe_join(settings.BERT_PRETRAINED_MODEL_DIRECTORY, file_name)  # Use safe_join to prevent path traversal attacks.
        rmtree(path)  # Since Pathlib can't deal with directories.
        return Response({"detail": f"Deleted model {model_name} from the filesystem!"}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=ApplyTaggerSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        """Apply BERT tagger to an Elasticsearch index."""
        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            tagger_object = self.get_object()
            new_task = Task.objects.create(berttagger=tagger_object, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
            tagger_object.save()

            tagger_object.tasks.add(new_task)

            project = Project.objects.get(pk=project_pk)
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            # indices = project.get_available_or_all_project_indices(indices)

            fields = serializer.validated_data["fields"]
            fact_name = serializer.validated_data["new_fact_name"]
            fact_value = serializer.validated_data["new_fact_value"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]
            es_timeout = serializer.validated_data["es_timeout"]

            if tagger_object.fact_name:
                # Disable fact_value usage for multiclass taggers
                fact_value = ""

            args = (pk, indices, fields, fact_name, fact_value, query, bulk_size, max_chunk_bytes, es_timeout)
            transaction.on_commit(lambda: apply_tagger_to_index.apply_async(args=args, queue=settings.CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying BERT Tagger with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)
