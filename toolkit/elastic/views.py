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

    def get_queryset(self):
        return Reindexer.objects.filter(project=self.kwargs['project_pk'])

    def create(self, request, *args, **kwargs):
        project_obj = Project.objects.get(id=self.kwargs['project_pk'])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validate_indices = self.validate_indices(serializer, self.request)
        validate_fields = self.validate_fields(self.request, serializer)
        if validate_indices and validate_fields:
            self.perform_create(serializer, project_obj)
            self.update_project_indices(serializer, project_obj)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        if not validate_indices:
            return Response({'error': f'The indices you are attempting to re-index are not contained in your project indices'}, status=status.HTTP_400_BAD_REQUEST)
        if not validate_fields:
            return Response({'error': f'The fields you are attempting to re-index are not contained in your project fields'}, status=status.HTTP_400_BAD_REQUEST)

    def perform_create(self, serializer, project_obj):
        serializer.save(
                        author=self.request.user,
                        project=project_obj,
                        fields=json.dumps(serializer.validated_data['fields']),
                        indices=json.dumps(serializer.validated_data['indices']))

    def validate_indices(self, serializer, request):
        ''' check if re-indexed index is in relevant project indices '''
        active_projects = Project.objects.filter(id=self.kwargs['project_pk'])
        project_indices = list(active_projects.values_list('indices', flat=True)) # gets [[index], ['index']]
        if self.request.data['indices'] not in project_indices:
            return False
        return True

    def validate_fields(self, request, serializer):
        ''' check if changed fields included in the request are in relevant project fields '''
        project_fields = ElasticCore().get_fields(indices=serializer.validated_data['indices'])
        field_data = [field["path"] for field in project_fields]
        request_fields = self.request.data['fields']
        for field in request_fields:
            if field not in field_data:
                return False
        return True

    def update_project_indices(self, serializer, project_obj):
        # probably have to replace this one as well
        project_indices = serializer.validated_data['indices']
        # print("serializer indices", project_indices)
        indices_to_add = [serializer.validated_data['new_index']]
        for index in indices_to_add:
            project_indices.append(index)
        project_obj.save(add_indices=project_indices)

