import json
import os

import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from celery.result import allow_join_result
from django.db import transaction

from toolkit.settings import CELERY_MLP_TASK_QUEUE, CELERY_LONG_TERM_TASK_QUEUE
from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.core.task.models import Task
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
from toolkit.mlp.tasks import apply_mlp_on_list
from toolkit.view_constants import BulkDelete, FavoriteModelViewMixing
from toolkit.exceptions import NonExistantModelError, SerializerNotValid
from .tasks import apply_crf_extractor, apply_crf_extractor_to_index
from .models import CRFExtractor
from .serializers import (
    CRFExtractorSerializer,
    CRFExtractorTagTextSerializer,
    ApplyCRFExtractorSerializer
)
from ..filter_constants import FavoriteFilter


class CRFExtractorFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('tasks__status', lookup_expr='icontains')


    class Meta:
        model = CRFExtractor
        fields = []


class CRFExtractorViewSet(viewsets.ModelViewSet, BulkDelete, FavoriteModelViewMixing):
    serializer_class = CRFExtractorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = CRFExtractorFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score', 'precision', 'recall', 'tasks__status')


    def get_queryset(self):
        return CRFExtractor.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)
        serializer.validated_data.pop("indices")

        extractor: CRFExtractor = serializer.save(
            author=self.request.user,
            project=project,
            labels=json.dumps(serializer.validated_data['labels']),
            c_values=json.dumps(serializer.validated_data['c_values']),
            suffix_len=json.dumps(serializer.validated_data['suffix_len'])
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            extractor.indices.add(index)

        extractor.train()


    def destroy(self, request, *args, **kwargs):
        instance: CRFExtractor = self.get_object()
        instance.delete()
        return Response({"success": "CRFExtractor instance deleted, model and plot removed"}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['get', 'post'])
    def list_features(self, request, pk=None, project_pk=None):
        """Returns list of features for the extactor."""
        extractor: CRFExtractor = self.get_object()
        # check if model exists
        if not extractor.model.path:
            raise NonExistantModelError()
        crf_model = extractor.load_extractor()
        feature_info = crf_model.get_features()
        return Response(feature_info, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        zip_name = f'crf_model_{pk}.zip'
        extractor: CRFExtractor = self.get_object()
        data = extractor.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data['file']
        crf_id = CRFExtractor.import_resources(uploaded_file, request, project_pk)
        return Response({"id": crf_id, "message": "Successfully imported model and associated files."}, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'])
    def retrain_extractor(self, request, pk=None, project_pk=None):
        """Starts retraining task for the Extractor model."""
        instance = self.get_object()
        instance.train()
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=CRFExtractorTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = CRFExtractorTagTextSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        # retrieve tagger object
        extractor: CRFExtractor = self.get_object()
        # check if tagger exists
        if not extractor.model.path:
            raise NonExistantModelError()
        # apply mlp
        text = serializer.validated_data["text"]
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": [text], "analyzers": extractor.mlp_analyzers}, queue=CELERY_MLP_TASK_QUEUE).get()
            mlp_document = mlp[0]
        # apply extractor
        extractor_response = apply_crf_extractor(
            extractor.id,
            mlp_document
        )
        return Response(extractor_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ApplyCRFExtractorSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        """Apply extrcator to an Elasticsearch index."""
        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            extractor = self.get_object()
            new_task = Task.objects.create(crfextractor=extractor, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
            extractor.save()

            extractor.tasks.add(new_task)

            indices = [index["name"] for index in serializer.validated_data["indices"]]
            mlp_fields = serializer.validated_data["mlp_fields"]
            label_suffix = serializer.validated_data["label_suffix"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]
            es_timeout = serializer.validated_data["es_timeout"]


            args = (pk, indices, mlp_fields, label_suffix, query, bulk_size, max_chunk_bytes, es_timeout)
            transaction.on_commit(lambda: apply_crf_extractor_to_index.apply_async(args=args, queue=CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying Tagger with id: {}".format(extractor.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)
