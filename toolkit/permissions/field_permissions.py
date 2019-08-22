from rest_framework import permissions
from toolkit.core.project.models import Project


class IsAdminUser(permissions.BasePermission):
    """
    Only superusers are permitted UNSAFE access this field. Safe access is permitted to all users.
    * Serializer field permissions do not take a view as an argument and they don't have an object_permission method *
    """
    message = 'Insufficient permissions for this project.'

    def has_permission(self, request):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)
