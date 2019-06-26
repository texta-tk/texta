from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query

from toolkit.neurotagger.models import Neurotagger
from toolkit.core.project.models import Project
from toolkit.neurotagger.serializers import NeurotaggerSerializer
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
from toolkit.utils.model_cache import ModelCache
from toolkit import permissions as toolkit_permissions
from toolkit.core import permissions as core_permissions

import json

# initialize model cache for neurotaggers
model_cache = ModelCache(NeurotaggerWorker)


def get_payload(request):
    if request.GET:
        data = request.GET
    elif request.POST:
        data = request.POST
    else:
        data = {}
    return data


class NeurotaggerViewSet(viewsets.ModelViewSet):
    serializer_class = NeurotaggerSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions,
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)

    def get_queryset(self):
        queryset = Neurotagger.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = Neurotagger.objects.filter(project=current_user.profile.active_project)
        return queryset


    def create(self, request, *args, **kwargs):
        serializer = NeurotaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
