from rest_framework import viewsets, permissions

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer

# TODO custom permission for project owner - >

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (permissions.IsAdminUser,)



