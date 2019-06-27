from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.word_cluster.serializers import WordClusterSerializer
from toolkit.word_cluster.models import WordCluster
from toolkit.core import permissions as core_permissions
from toolkit import permissions as toolkit_permissions

import json

class WordClusterViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA embedding clusterings to be viewed or edited.
    Only include embedding clusterings that are related to the request UserProfile's active_project
    """
    serializer_class = WordClusterSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions, 
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
    )

    def get_queryset(self):
        queryset = WordCluster.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = WordCluster.objects.filter(project=current_user.profile.active_project)
        return queryset
    
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)
