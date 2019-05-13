from rest_framework import viewsets

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer


# Create your views here.
class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
