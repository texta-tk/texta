from django.db.models.query import QuerySet
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from toolkit.core.project import permissions as project_permissions
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (project_permissions.ProjectPermissions, permissions.IsAuthenticated)
    
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def get_queryset(self):
        queryset = self.queryset
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = queryset.filter(owner=current_user) | queryset.filter(users=current_user)
        return queryset

    @action(detail=True, methods=['get'])
    def activate_project(self, request, pk=None):
        obj = self.get_object()
        request.user.profile.activate_project(obj)
        return Response({'status': f'Project {pk} successfully activated.'}, status=status.HTTP_200_OK)
