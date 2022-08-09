import json

import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import mixins, permissions, viewsets

from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.elastic.index_splitter.models import IndexSplitter
from toolkit.elastic.index_splitter.serializers import IndexSplitterSerializer
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.view_constants import BulkDelete


class IndexSplitterViewSet(mixins.CreateModelMixin,
                           mixins.ListModelMixin,
                           mixins.RetrieveModelMixin,
                           mixins.DestroyModelMixin,
                           viewsets.GenericViewSet,
                           BulkDelete):
    """
    create:
    Creates index_splitter task object.
    """
    queryset = IndexSplitter.objects.all()
    serializer_class = IndexSplitterSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)

    ordering_fields = ('id', 'author__username', 'description', 'fields', 'custom_distribution', 'train_index', 'test_index' 'indices', 'scroll_size',)


    def get_queryset(self):
        return IndexSplitter.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer: IndexSplitterSerializer):
        project_obj = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_obj.get_available_or_all_project_indices(indices)
        serializer.validated_data.pop("indices")

        splitter_model = serializer.save(
            author=self.request.user,
            project=project_obj,
            fields=json.dumps(serializer.validated_data.get('fields', []))
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            splitter_model.indices.add(index)

        self.update_project_indices(serializer, project_obj, self.request)
        splitter_model.start_task()


    def update_project_indices(self, serializer, project_obj, request):
        ''' add new_index included in the request to the relevant project object '''
        train_ix_name = serializer.validated_data['train_index']
        train_ix, is_open = Index.objects.get_or_create(name=train_ix_name, defaults={"added_by": request.user.username})
        test_ix_name = serializer.validated_data['test_index']
        test_ix, is_open = Index.objects.get_or_create(name=test_ix_name, defaults={"added_by": request.user.username})
        project_obj.indices.add(train_ix)
        project_obj.indices.add(test_ix)
        project_obj.save()
