from rest_framework import permissions
from toolkit.core.project.models import Project

class ProjectAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this project.'

    def has_object_permission(self, request, view, obj):
        # retrieve project object
        project_object = Project.objects.get(id=view.kwargs['pk'])
        # check if user is owner or listed in project users
        if request.user in project_object.users.all() or request.user == project_object.owner:
            return True
        # check if user is superuser
        if request.user.is_superuser:
            return True
        # nah, not gonna see anything!
        return False
