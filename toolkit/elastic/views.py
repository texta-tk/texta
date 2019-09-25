from toolkit.elastic.serializers import ReindexerCreateSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from rest_framework import viewsets, permissions
from toolkit.core.project.models import Project
from toolkit.elastic.models import Reindexer
from rest_framework.response import Response
from rest_framework.decorators import action
import json


# TODO serve Task progress
class ReindexerViewSet(viewsets.ModelViewSet):
    queryset = Reindexer.objects.all()
    serializer_class = ReindexerCreateSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
        )

    def get_serializer_class(self):
        if self.request.method == 'PUT':
            return ReindexerUpdateSerializer
        return ReindexerCreateSerializer

    def perform_create(self, serializer):
        serializer.save(
                        author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']),
                        indices=json.dumps(serializer.validated_data['indices']))

    # TODO: also serve fields
    @action(detail=False, methods=['get'])
    def get_indices(self, request, pk=None, project_pk=None):
        project_object = Project.objects.filter(id=self.kwargs['project_pk'])
        indices = project_object.values("indices")
        return Response(indices.first())



