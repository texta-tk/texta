from rest_framework import permissions
from toolkit.core.project.models import Project

class ProjectAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this project.'

    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)

    def _permission_check(self, request, view):
        # always permit SAFE_METHODS and superuser
        if request.user.is_superuser or request.method in permissions.SAFE_METHODS:
            return True
        # retrieve project object
        try:
            project_object = Project.objects.get(id=view.kwargs['pk'])
        except:
            return False
        if request.user in project_object.users.all() and request.method in permissions.SAFE_METHODS:
            return True
        # if user is owner, allow UNSAFE_METHODS
        return project_object.owner == request.user
