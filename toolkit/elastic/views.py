from rest_framework import status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
import json

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer
from toolkit.elastic.models import Reindexer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.serializers import ReindexerCreateSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed


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

    # get_queryset to render user specific tasks in listview.
    def get_queryset(self):
        return Reindexer.objects.filter(project=self.kwargs['project_pk'])

    def create(self, request, *args, **kwargs):
        # TODO, validate fields
        project_obj = Project.objects.get(id=self.kwargs['project_pk'])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # before the model is created, validate indices and fields
        if self.validate_indices(self.request):
            self.perform_create(serializer, project_obj)
            self.update_project_indices(serializer, project_obj)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        return Response({'error': f'insufficient permissions to re-index'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer, project_obj):
        serializer.save(
                        author=self.request.user,
                        project=project_obj,
                        fields=json.dumps(serializer.validated_data['fields']),
                        indices=json.dumps(serializer.validated_data['indices']))

    def validate_indices(self, request):
        active_project = Project.objects.filter(id=self.kwargs['project_pk'])
        project_indices = list(active_project.values_list('indices', flat=True))
        if self.request.data['indices'] not in project_indices:
            return False
        return True

    def update_project_indices(self, serializer, project_obj):
        project_indices = serializer.validated_data['indices']
        indices_to_add = [serializer.validated_data['new_index']]
        for index in indices_to_add:
            project_indices.append(index)
        project_obj.save(add_indices=project_indices)


