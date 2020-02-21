# Create your views here.
import json

from rest_framework import permissions, viewsets

from toolkit.core.project.models import Project
from toolkit.mlp.models import MLPProcessor
from toolkit.mlp.serializers import MLPElasticSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete


class MLPElasticViewset(viewsets.ModelViewSet, BulkDelete):
    queryset = MLPProcessor.objects.all()
    serializer_class = MLPElasticSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )


    def perform_create(self, serializer):
        project_obj = Project.objects.get(id=self.kwargs['project_pk'])

        serializer.save(
            author=self.request.user,
            project=project_obj,
            fields=json.dumps(serializer.validated_data['fields']),
            indices=json.dumps(serializer.validated_data['indices']),
        )


    def get_queryset(self):
        return MLPProcessor.objects.filter(project=self.kwargs['project_pk'])
