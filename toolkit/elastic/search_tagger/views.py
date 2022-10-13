import json
from toolkit.view_constants import BulkDelete
from .serializers import SearchQueryTaggerSerializer, SearchFieldsTaggerSerializer
from rest_framework import permissions, viewsets
import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from .models import SearchQueryTagger, SearchFieldsTagger
from django.db import transaction
from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index


class SearchQueryTaggerViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = SearchQueryTaggerSerializer
    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = (
        'id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score',
        'precision', 'recall', 'tasks__status')
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )


    def get_queryset(self):
        return SearchQueryTagger.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        with transaction.atomic():
            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)
            serializer.validated_data.pop("indices")

            worker: SearchQueryTagger = serializer.save(
                author=self.request.user,
                project=project,
                fields=json.dumps(serializer.validated_data["fields"]),
                query=json.dumps(serializer.validated_data["query"], ensure_ascii=False),
            )
            for index in Index.objects.filter(name__in=indices, is_open=True):
                worker.indices.add(index)
            worker.process()


class SearchFieldsTaggerViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = SearchFieldsTaggerSerializer
    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = (
        'id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score',
        'precision', 'recall', 'tasks__status')
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )


    def get_queryset(self):
        return SearchFieldsTagger.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        with transaction.atomic():
            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)
            serializer.validated_data.pop("indices")

            worker: SearchFieldsTagger = serializer.save(
                author=self.request.user,
                project=project,
                fields=json.dumps(serializer.validated_data["fields"]),
                query=json.dumps(serializer.validated_data["query"], ensure_ascii=False),
            )
            for index in Index.objects.filter(name__in=indices, is_open=True):
                worker.indices.add(index)
            worker.process()
