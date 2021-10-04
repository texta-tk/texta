import json
import os

import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CRFExtractor
from .serializers import CRFExtractorSerializer

from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
#from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE
#from toolkit.tagger.validators import validate_input_document
from toolkit.view_constants import BulkDelete



class CRFExtractorFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')


    class Meta:
        model = CRFExtractor
        fields = []


class CRFExtractorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = CRFExtractorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = CRFExtractorFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


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
            labels=json.dumps(serializer.validated_data['labels'])
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

        extractor: Extractor = self.get_object()
        # check if model exists
        if not extractor.model.path:
            raise NonExistantModelError()



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
