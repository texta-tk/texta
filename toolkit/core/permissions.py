from rest_framework import viewsets, permissions
from toolkit.core.project.models import Project


class ProjectPermissions(permissions.BasePermission):

    def has_object_permission(self, request, view, obj):
        # always allow (GET, HEAD or OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        owned_projects = Project.objects.filter(owner=request.user.id)
        if obj in owned_projects or request.user.is_superuser:
            return True
        else:
            return False
