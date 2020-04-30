import json

import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import JsonResponse
from django_filters import rest_framework as filters
from rest_auth import views
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.exceptions import ElasticIndexAlreadyExists
from toolkit.elastic.models import Index, Reindexer
from toolkit.elastic.serializers import IndexSerializer, ReindexerCreateSerializer
from toolkit.pagination import PageNumberPaginationDataOnly
from toolkit.permissions.project_permissions import IsSuperUser, ProjectResourceAllowed
from toolkit.view_constants import BulkDelete


class IndicesFilter(filters.FilterSet):
    id = filters.CharFilter('id', lookup_expr='exact')
    name = filters.CharFilter('name', lookup_expr='icontains')
    is_open = filters.BooleanFilter("is_open")


    class Meta:
        model = Index
        fields = []


class ElasticGetIndices(views.APIView):
    permission_classes = (IsSuperUser,)


    def get(self, request):
        """
        Returns **all** available indices from Elasticsearch.
        This is different from get_indices action in project view as it lists **all** indices in Elasticsearch.
        """
        es_core = ElasticCore()
        es_core.syncher()
        indices = [index.name for index in Index.objects.all()]
        return JsonResponse(indices, safe=False, status=status.HTTP_200_OK)


class IndexViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    queryset = Index.objects.all()
    serializer_class = IndexSerializer
    permission_classes = [IsSuperUser]

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    pagination_class = None
    filterset_class = IndicesFilter

    ordering_fields = (
        'id',
        'name',
        'is_open'
    )


    def list(self, request, *args, **kwargs):
        ec = ElasticCore()
        ec.syncher()
        response = super(IndexViewSet, self).list(request, *args, **kwargs)

        data = response.data  # Get the paginated and sorted queryset results.
        open_indices = [index for index in data if index["is_open"]]
        # We don't want to ping closed indices, otherwise we get an Elasticsearch side error.
        stats = ec.get_index_stats(indices=[index["name"] for index in open_indices])

        # Update the paginated and sorted queryset results.
        for index in response.data:
            name = index["name"]
            is_open = index["is_open"]
            if is_open:
                index.update(**stats[name])
            else:
                # For the sake of courtesy on the front-end, make closed indices values zero.
                index.update(size=0, doc_count=0)

        return response


    def retrieve(self, request, *args, **kwargs):
        ec = ElasticCore()
        response = super(IndexViewSet, self).retrieve(*args, *kwargs)
        if response.data["is_open"]:
            index_name = response.data["name"]
            stats = ec.get_index_stats(indices=[index_name])
            response.data.update(**stats[index_name])
        else:
            response.data.update(size=0, doc_count=0)

        return response


    def create(self, request, **kwargs):
        data = IndexSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        es = ElasticCore()
        index = data.validated_data["name"]
        is_open = data.validated_data["is_open"]

        # Using get_or_create to avoid unique name constraints on creation.
        if es.check_if_indices_exist([index]):
            # Even if the index already exists, create the index object just in case
            index, is_created = Index.objects.get_or_create(name=index)
            if is_created: index.is_open = is_open
            index.save()
            raise ElasticIndexAlreadyExists()

        else:
            index, is_created = Index.objects.get_or_create(name=index)
            if is_created: index.is_open = is_open
            index.save()

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
        ElasticCore().syncher()
        return Response({"message": "Synched everything successfully!"}, status=status.HTTP_204_NO_CONTENT)


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
