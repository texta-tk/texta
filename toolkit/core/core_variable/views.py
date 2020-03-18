from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ...permissions.project_permissions import IsSuperUser
from .models import CoreVariable
from .serializers import CoreVariableSerializer


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer
    permission_classes = (
        IsSuperUser,
    )

    def get_queryset(self):
        return CoreVariable.objects.all()
