import os
import json
import numpy as np

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.torchtagger.models import TorchTagger
from toolkit.core.project.models import Project
from toolkit.torchtagger.serializers import TorchTaggerSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete, ExportModel


class TorchTaggerViewSet(viewsets.ModelViewSet, BulkDelete, ExportModel):
    serializer_class = TorchTaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
        )

    def perform_create(self, serializer, **kwargs):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']),
                        **kwargs)

    def get_queryset(self):
        return TorchTagger.objects.filter(project=self.kwargs['project_pk'])
