from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ...permissions.project_permissions import IsSuperUser
from .models import EnvironmentVariable
from .serializers import EnvironmentVariableSerializer


class EnvironmentVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = EnvironmentVariableSerializer
    permission_classes = (
        IsSuperUser,
    )

    def get_queryset(self):
        return EnvironmentVariable.objects.all()
