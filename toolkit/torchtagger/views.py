import os
import json
import numpy as np

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.torchtagger.torchtagger import TorchTagger
from toolkit.core.project.models import Project
from toolkit.torchtagger.serializers import TorchTaggerSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete, ExportModel
from toolkit.serializer_constants import GeneralTextSerializer
from toolkit.tools.model_cache import ModelCache

from django_filters import rest_framework as filters
import rest_framework.filters as drf_filters

global_torchtagger_cache = ModelCache(TorchTagger)

class TorchTaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')

    class Meta:
        model = TorchTaggerObject
        fields = []


class TorchTaggerViewSet(viewsets.ModelViewSet, BulkDelete, ExportModel):
    serializer_class = TorchTaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
        )
    
    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TorchTaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


    def perform_create(self, serializer, **kwargs):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']),
                        **kwargs)

    def get_queryset(self):
        return TorchTaggerObject.objects.filter(project=self.kwargs['project_pk'])

    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = GeneralTextSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve model from cache
        tagger = global_torchtagger_cache.get_model(tagger_object)

        tagger_response = tagger.tag_text(serializer.validated_data['text'])
        return Response(tagger_response, status=status.HTTP_200_OK)
