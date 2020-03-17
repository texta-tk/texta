from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import EnvironmentVariable
from .serializers import EnvironmentVariableSerializer


class EnvironmentVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = EnvironmentVariableSerializer
    permission_classes = (
        permissions.IsSuperUser,
    )
