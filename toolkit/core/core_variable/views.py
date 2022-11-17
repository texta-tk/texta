from rest_framework import viewsets

from .models import CoreVariable
from .serializers import CoreVariableSerializer
from ...permissions.project_permissions import IsSuperUser


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer
    permission_classes = (
        IsSuperUser,
    )

    def get_queryset(self):
        return CoreVariable.objects.all()
