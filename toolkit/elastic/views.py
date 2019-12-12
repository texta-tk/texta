from rest_framework import status, views, viewsets, mixins, permissions
from rest_framework.response import Response
from rest_framework.decorators import action
import json

from toolkit.exceptions import ProjectValidationFailed
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer
from toolkit.elastic.models import Reindexer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.serializers import ReindexerCreateSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed, IsSuperUser
from toolkit.view_constants import BulkDelete

from django_filters import rest_framework as filters
import rest_framework.filters as drf_filters


class ElasticGetIndices(views.APIView):
    permission_classes = (IsSuperUser,)


    def get(self, request):
        """
        Returns **all** available indices from Elasticsearch.
        This is different from get_indices action in project view as it lists **all** indices in Elasticsearch.
        """
        es_core = ElasticCore()
        if not es_core.connection:
            return Response({"error": "no connection to Elasticsearch"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        indices = sorted(ElasticCore().get_indices())
        return Response(indices, status=status.HTTP_200_OK)


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
        self.update_project_indices(serializer, project_obj, project_obj.indices)

    def update_project_indices(self, serializer, project_obj, project_indices):
        ''' add new_index included in the request to the relevant project object '''
        indices_to_add = [serializer.validated_data['new_index']]
        for index in indices_to_add:
            project_indices.append(index)
        project_obj.save(add_indices=project_indices)
