from rest_framework import permissions

class HasActiveProject(permissions.BasePermission):
    message = 'A project must be activated.'

    def has_permission(self, request, view):
        return request.user.profile.active_project is not None
