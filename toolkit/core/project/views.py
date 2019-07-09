from django.db.models.query import QuerySet
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from toolkit.core.project import permissions as project_permissions
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer
from toolkit.elastic.core import ElasticCore


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (
        project_permissions.ProjectAllowed, 
        permissions.IsAuthenticated
    )
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


    def get_queryset(self):
        queryset = Project.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = queryset.filter(owner=current_user) | queryset.filter(users=current_user)
        return queryset


    @action(detail=True, methods=['get', 'post'])
    def get_fields(self, request, pk=None, project_pk=None):
        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)
        fields = ElasticCore().get_fields(indices=project_indices)
        field_map = {}
        for field in fields:
            if field['index'] not in field_map:
                field_map[field['index']] = []
                field_info = dict(field)
                del field_info['index']
            field_map[field['index']].append(field_info)
        return Response(field_map, status=status.HTTP_200_OK)
