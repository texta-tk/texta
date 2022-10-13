import json

import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import permissions, status, views, viewsets
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.analyzers.models import ApplyESAnalyzerWorker
from toolkit.elastic.analyzers.serializers import ApplyESAnalyzerWorkerSerializer, SnowballSerializer
from toolkit.elastic.choices import get_snowball_choices
from toolkit.elastic.index.models import Index
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.tools.lemmatizer import ElasticAnalyzer
from toolkit.view_constants import BulkDelete


class SnowballProcessor(views.APIView):
    serializer_class = SnowballSerializer
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = SnowballSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        language = serializer.validated_data["language"]

        lemmatizer = ElasticAnalyzer(language=language)
        lemmatized = lemmatizer.stem_text(text, language=language)

        return Response({"text": lemmatized, "language": language})


    def get(self, request):
        languages = get_snowball_choices()
        languages = [key for key, value in languages]
        return Response(languages, status=status.HTTP_200_OK)


class ApplyEsAnalyzerOnIndices(viewsets.ModelViewSet, BulkDelete):
    serializer_class = ApplyESAnalyzerWorkerSerializer

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description', 'detect_lang', 'fields', 'tasks__time_started', 'tasks__time_completed', 'tasks__status')

    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated
    )


    def get_queryset(self):
        return ApplyESAnalyzerWorker.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")

        worker: ApplyESAnalyzerWorker = serializer.save(
            author=self.request.user,
            project=project,
            fields=json.dumps(serializer.validated_data["fields"], ensure_ascii=False),
            analyzers=json.dumps(list(serializer.validated_data["analyzers"])),
            query=json.dumps(serializer.validated_data["query"], ensure_ascii=False)
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            worker.indices.add(index)

        worker.process()
