from rest_framework import permissions, viewsets

from toolkit.core.project.models import Project
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.view_constants import BulkDelete
from .models import DatasetImport
from .serializers import DatasetImportSerializer


class DatasetImportViewSet(viewsets.ModelViewSet, BulkDelete):
    queryset = DatasetImport.objects.all()
    serializer_class = DatasetImportSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )


    def get_queryset(self):
        return DatasetImport.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        dataset_import: DatasetImport = serializer.save(
            author=self.request.user,
            project=Project.objects.get(id=self.kwargs['project_pk']),
            index=serializer.validated_data['index'],
            file=serializer.validated_data['file']
        )
        dataset_import.start_import()
