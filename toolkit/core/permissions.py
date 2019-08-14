from rest_framework import viewsets, permissions
from toolkit.core.project.models import Project

class ProjectResourceAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this resource.'

    """
    All authenticated users can create new projects
    All project users, and the project owner can perform SAFE and UNSAFE_METHODS on project resources.
    Superuser has no restrictions.
    If current_user is not a project user or owner, the project is filtered out in the queryset. So in most or all cases ProjectResourcepermissions
    are not actually required. With future use cases, however, they may become useful.

    """

    def has_permission(self, request, view):
        return self._permission_check(request, view)

    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)

    def _permission_check(self, request, view):
        # retrieve project object
        try:
            project_object = Project.objects.get(id=view.kwargs['project_pk'])
        except:
            return False
        # check if user is owner or listed in project users
        if request.user in project_object.users.all() or request.user == project_object.owner:
            return True
        # check if user is superuser
        if request.user.is_superuser:
            return True
        # nah, not gonna see anything!
        return False
