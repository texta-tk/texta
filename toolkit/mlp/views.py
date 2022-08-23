# Create your views here.
import json

import rest_framework.filters as drf_filters
from celery.result import allow_join_result
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.renderers import BrowsableAPIRenderer, HTMLFormRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.views import APIView
from texta_mlp.mlp import MLP

from toolkit.core.project.models import Project
from toolkit.elastic.choices import ES6_SNOWBALL_MAPPING, ES7_SNOWBALL_MAPPING
from toolkit.elastic.index.models import Index
from toolkit.mlp.exceptions import CouldNotDetectLanguageException, WorkerBusyException
from toolkit.mlp.models import ApplyLangWorker, MLPWorker
from toolkit.mlp.serializers import ApplyLangOnIndicesSerializer, LangDetectSerializer, MLPDocsSerializer, MLPListSerializer, MLPWorkerSerializer
from toolkit.mlp.tasks import apply_mlp_on_docs, apply_mlp_on_list
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.settings import CELERY_MLP_TASK_QUEUE
from toolkit.view_constants import BulkDelete
from toolkit.mlp.helpers import check_celery_tasks


class LangDetectView(APIView):
    """
    Given any input text it returns the ISO 639-1 two letter language code and a more humanized
    version of the language if that language is supported by Elasticsearch Snowball Stemmer, otherwise
    it will be null.
    """
    serializer_class = LangDetectSerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)


    def _enrich_language_info(self, text: str, language: str):
        mapping = {**ES6_SNOWBALL_MAPPING, **ES7_SNOWBALL_MAPPING}
        result = {
            "text": text,
            "language_code": language,
            "language": None
        }
        if language in mapping:
            result["language"] = mapping.get(language, None)
        return result


    def post(self, request):
        serializer = LangDetectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data["text"]
        language = MLP.detect_language("", text)
        if language:
            result = self._enrich_language_info(text, language)
            return Response(result, status=status.HTTP_200_OK)
        else:
            raise CouldNotDetectLanguageException()


class MlpDocsProcessor(APIView):
    serializer_class = MLPDocsSerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = MLPDocsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        docs = list(serializer.validated_data["docs"])
        analyzers = list(serializer.validated_data["analyzers"])
        fields_to_parse = list(serializer.validated_data["fields_to_parse"])

        # check if the MLP queue is empty to process our request
        if not check_celery_tasks(CELERY_MLP_TASK_QUEUE):
            raise WorkerBusyException()

        with allow_join_result():
            mlp = apply_mlp_on_docs.apply_async(kwargs={"docs": docs, "analyzers": analyzers, "fields_to_parse": fields_to_parse}, queue=CELERY_MLP_TASK_QUEUE).get()
        return Response(mlp)


class MLPListProcessor(APIView):
    serializer_class = MLPListSerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = MLPListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        texts = list(serializer.validated_data["texts"])
        analyzers = list(serializer.validated_data["analyzers"])

        # check if the MLP queue is empty to process our request
        if not check_celery_tasks(CELERY_MLP_TASK_QUEUE):
            raise WorkerBusyException()
        
        with allow_join_result():
            mlp = apply_mlp_on_list.apply_async(kwargs={"texts": texts, "analyzers": analyzers}, queue=CELERY_MLP_TASK_QUEUE).get()
        return Response(mlp)



class MLPElasticWorkerViewset(viewsets.ModelViewSet, BulkDelete):
    serializer_class = MLPWorkerSerializer

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'tasks__status')

    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated
    )


    def get_queryset(self):
        return MLPWorker.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        with transaction.atomic():
            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)
            analyzers = list(serializer.validated_data["analyzers"])

            serializer.validated_data.pop("indices")

            worker: MLPWorker = serializer.save(
                author=self.request.user,
                project=project,
                fields=json.dumps(serializer.validated_data["fields"], ensure_ascii=False),
                analyzers=json.dumps(analyzers),
                query=json.dumps(serializer.validated_data["query"], ensure_ascii=False)
            )

            for index in Index.objects.filter(name__in=indices, is_open=True):
                worker.indices.add(index)

            worker.process()


class ApplyLangOnIndices(viewsets.ModelViewSet, BulkDelete):
    serializer_class = ApplyLangOnIndicesSerializer

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'tasks__status')

    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated
    )


    def get_queryset(self):
        return ApplyLangWorker.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        with transaction.atomic():
            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)

            serializer.validated_data.pop("indices")

            worker: ApplyLangWorker = serializer.save(
                author=self.request.user,
                project=project,
            )

            for index in Index.objects.filter(name__in=indices, is_open=True):
                worker.indices.add(index)

            worker.process()
