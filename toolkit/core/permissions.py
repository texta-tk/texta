from rest_framework import viewsets, permissions
from toolkit.core.project.models import Project
from toolkit.tagger.models import Tagger

class TaggerEmbeddingsPermissions(permissions.BasePermission):
    message = 'Insufficient permissions for this object.'
    # TODO appears to be a problem with rights for 'user'

    def has_object_permission(self, request, view, obj):
        # always allow (GET, HEAD or OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True

        owned_projects = Project.objects.filter(owner=request.user.id)
        if obj.project in owned_projects or request.user.is_superuser:
            return True
        else:
            return False


class EmbeddingFiltering(permissions.BasePermission):
    # TODO
    pass

    # def has_permission(self, request, view):
