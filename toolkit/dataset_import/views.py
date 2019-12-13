from rest_framework import status, views, viewsets, mixins, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters import rest_framework as filters
import rest_framework.filters as drf_filters

from .models import DatasetImport
from .serializers import DatasetImportSerializer
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete

class DatasetImportViewSet(viewsets.ModelViewSet, BulkDelete):
    queryset = DatasetImport.objects.all()
    serializer_class = DatasetImportSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    def get_queryset(self):
        return DatasetImport.objects.filter(project=self.kwargs['project_pk'])

    def perform_create(self, serializer):
        dataset_import: DatasetImport = serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        index=serializer.validated_data['index'],
                        file=serializer.validated_data['file'])
        dataset_import.start_import()
