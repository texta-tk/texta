# Create your views here.
import json

import rest_framework.filters as drf_filters
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import permissions, viewsets
from rest_framework.renderers import BrowsableAPIRenderer, HTMLFormRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView

from toolkit.core.project.models import Project
from toolkit.elastic.models import Index
from toolkit.mlp.models import MLPWorker
from toolkit.mlp.serializers import MLPDocsSerializer, MLPListSerializer, MLPWorkerSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.taskman import mlp_task
from toolkit.view_constants import BulkDelete


class MlpDocsProcessor(APIView):
    serializer_class = MLPDocsSerializer
    renderer_classes = (BrowsableAPIRenderer, JSONRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = MLPDocsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        docs = serializer.validated_data["docs"]
        analyzers = serializer.validated_data["analyzers"]
        fields_to_parse = serializer.validated_data["fields_to_parse"]

        data = mlp_task.apply(args=("doc",), kwargs={"docs": docs, "analyzers": analyzers, "fields_to_parse": fields_to_parse}, queue="mlp_queue").get()

        return Response(data)


class MLPListProcessor(APIView):
    serializer_class = MLPListSerializer
    renderer_classes = (BrowsableAPIRenderer, JSONRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = MLPListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        texts = serializer.validated_data["texts"]
        analyzers = serializer.validated_data["analyzers"]

        data = mlp_task.apply(args=("list",), kwargs={"texts": texts, "analyzers": analyzers}, queue="mlp_queue").get()

        return Response(data)


class MLPElasticWorkerViewset(viewsets.ModelViewSet, BulkDelete):
    serializer_class = MLPWorkerSerializer

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')

    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated
    )


    def get_queryset(self):
        return MLPWorker.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer):
        with transaction.atomic():
            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)

            serializer.validated_data.pop("indices")

            worker: MLPWorker = serializer.save(
                author=self.request.user,
                project=project,
                fields=json.dumps(serializer.validated_data["fields"]),
                query=json.dumps(serializer.validated_data["query"]),
                analyzers=json.dumps(serializer.validated_data["analyzers"]),
            )

            for index in Index.objects.filter(name__in=indices, is_open=True):
                worker.indices.add(index)

            worker.process()
