from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from toolkit.core.lexicon.models import Lexicon
from toolkit.core.lexicon.serializers import LexiconSerializer
from toolkit import permissions as toolkit_permissions
from toolkit.core import permissions as core_permissions


class LexiconViewSet(viewsets.ModelViewSet):
    serializer_class = LexiconSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions,
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)

    def get_queryset(self):
        queryset = Lexicon.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = Lexicon.objects.filter(project=current_user.profile.active_project)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = LexiconSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
