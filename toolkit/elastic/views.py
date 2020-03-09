import json

import rest_framework.filters as drf_filters
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.models import Index, Reindexer
from toolkit.elastic.serializers import IndexSerializer, ReindexerCreateSerializer
from toolkit.permissions.project_permissions import IsSuperUser, ProjectResourceAllowed
from toolkit.view_constants import BulkDelete


class IndexViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    queryset = Index.objects.all()
    serializer_class = IndexSerializer
    permission_classes = [IsSuperUser]


    def list(self, request, *args, **kwargs):
        ElasticCore.syncher()
        return super(IndexViewSet, self).list(request, *args, **kwargs)


    def create(self, request, **kwargs):
        data = IndexSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        index = data.validated_data["name"]
        is_open = data.validated_data["is_open"]

        # Using get_or_create to avoid unique name constraints on creation.
        # When using the same name, the default behaviour is to only change the is_open value.
        index = Index.objects.get_or_create(name=index)
        index = index[0] if isinstance(index, tuple) else index
        index.is_open = is_open
        index.save()

        es = ElasticCore()
        es.create_index(index=index)
        if not is_open: es.close_index(index)
        return Response({"message": f"Added index {index} into Elasticsearch!"}, status=status.HTTP_201_CREATED)


    def destroy(self, request, pk=None, **kwargs):
        with transaction.atomic():
            index_name = Index.objects.get(pk=pk).name
            es = ElasticCore()
            es.delete_index(index_name)
            Index.objects.filter(pk=pk).delete()
            return Response({"message": f"Deleted index {index_name} from Elasticsearch!"})




    @action(detail=False, methods=['post'])
    def sync_indices(self, request, pk=None, project_pk=None):
        return ElasticCore.syncher()


    @action(detail=True, methods=['patch'])
    def close_index(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        es_core.close_index(index.name)
        index.is_open = False
        index.save()
        return Response({"message": f"Closed the index {index.name}"})


    @action(detail=True, methods=['patch'])
    def open_index(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        es_core.open_index(index.name)
        if not index.is_open:
            index.is_open = True
            index.save()

        return Response({"message": f"Opened the index {index.name}"})


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
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = ReindexerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'new_index', 'indices', 'random_size',
                       'task__time_started', 'task__time_completed',
                       'task__status')


    def get_queryset(self):
        return Reindexer.objects.filter(project=self.kwargs['project_pk'])


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
