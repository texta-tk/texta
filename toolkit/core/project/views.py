from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer
from toolkit.core.user_profile.serializers import UserProfileSerializer

# TODO custom permission for project owner - >

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (permissions.IsAdminUser,)

    @action(detail=True, methods=['put'])
    def activate_project(self, request, pk=None):
        obj = self.get_object()
        request.user.profile.activate_project(obj)
        return Response({'status': f'Project {pk} successfully activated.'}, status=status.HTTP_200_OK)
