from rest_framework import viewsets, permissions
from toolkit.core.project.models import Project

"""
    All authenticated users can create new projects
    All project users, and the project owner can perform SAFE and UNSAFE_METHODS on project resources.
    Superuser has no restrictions.
    If current_user is not a project user or owner, the project is filtered out in the queryset. So in most or all cases ProjectResourceAllowed permissions
    are not actually required. With future use cases, however, they may become useful.
"""


class ProjectResourceAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this resource.'

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
        # check if user is listed among project users
        if request.user in project_object.users.all():
            return True
        # check if user is superuser
        if request.user.is_superuser:
            return True
        # nah, not gonna see anything!
        return False


class ProjectAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this project.'

    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)

    def _permission_check(self, request, view):
        # always permit SAFE_METHODS and superuser
        if request.user.is_superuser:
            return True
        # retrieve project object
        try:
            project_object = Project.objects.get(id=view.kwargs['pk'])
        except:
            return False
        # project users are permitted safe access to project list_view
        if request.user in project_object.users.all() and request.method in permissions.SAFE_METHODS:
            return True
        return False


class IsSuperUser(permissions.BasePermission):


    def has_permission(self, request, view):
        return self._permission_check(request, view)

    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)

    def _permission_check(self, request, view):
        return request.user and request.user.is_superuser


class ExtraActionResource(ProjectResourceAllowed):
    """ Overrides ProjectResourceAllowed """

    def _permission_check(self, request, view):
        # retrieve project object
        try:
            project_object = Project.objects.get(id=view.kwargs['pk'])
        except:
            return False
        # check if user is listed among project users
        if request.user in project_object.users.all():
            return True
        # check if user is superuser
        if request.user.is_superuser:
            return True
        # nah, not goa see anything!
        return False









