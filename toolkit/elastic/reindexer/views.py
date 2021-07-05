import json

import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, viewsets

from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.elastic.reindexer.serializers import ReindexerCreateSerializer
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.view_constants import BulkDelete


class ReindexerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')


    class Meta:
        model = Reindexer
        fields = []


class ReindexerViewSet(mixins.CreateModelMixin,
                       mixins.ListModelMixin,
                       mixins.RetrieveModelMixin,
                       mixins.DestroyModelMixin,
                       viewsets.GenericViewSet,
                       BulkDelete):
    """
    list:
    Returns list of reindexing task objects.

    read:
    Return  reindexing task object by id.

    create:
    Creates  reindexing task object.

    delete:
    Deletes reindexing task object.
    """
    queryset = Reindexer.objects.all()
    serializer_class = ReindexerCreateSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = ReindexerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'new_index', 'indices', 'random_size',
                       'task__time_started', 'task__time_completed',
                       'task__status')


    def get_queryset(self):
        return Reindexer.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project_obj = Project.objects.get(id=self.kwargs['project_pk'])
        serializer.save(
            author=self.request.user,
            project=project_obj,
            field_type=json.dumps(serializer.validated_data.get('field_type', [])),
            fields=json.dumps(serializer.validated_data.get('fields', [])),
            indices=json.dumps(serializer.validated_data['indices']))
        self.update_project_indices(serializer, project_obj)


    def update_project_indices(self, serializer, project_obj):
        ''' add new_index included in the request to the relevant project object '''
        indices_to_add = serializer.validated_data['new_index']
        index, is_open = Index.objects.get_or_create(name=indices_to_add)
        project_obj.indices.add(index)
        project_obj.save()
