import json

import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_auth import views
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.choices import get_snowball_choices
from toolkit.elastic.index.models import Index
from toolkit.elastic.snowball.models import ApplyStemmerWorker
from toolkit.elastic.snowball.serializers import ApplySnowballSerializer, SnowballSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.tools.lemmatizer import ElasticLemmatizer
from toolkit.view_constants import BulkDelete


class SnowballProcessor(views.APIView):
    serializer_class = SnowballSerializer
    permission_classes = (permissions.IsAuthenticated,)


    def post(self, request):
        serializer = SnowballSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        language = serializer.validated_data["language"]

        lemmatizer = ElasticLemmatizer(language=language)
        lemmatized = lemmatizer.lemmatize(text)

        return Response({"text": lemmatized})


    def get(self, request):
        languages = get_snowball_choices()
        languages = [key for key, value in languages]
        return Response(languages, status=status.HTTP_200_OK)


class ApplySnowballOnIndices(viewsets.ModelViewSet, BulkDelete):
    serializer_class = ApplySnowballSerializer

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description', 'detect_lang', 'fields', 'task__time_started', 'task__time_completed', 'task__status')

    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated
    )


    def get_queryset(self):
        return ApplyStemmerWorker.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")

        worker: ApplyStemmerWorker = serializer.save(
            author=self.request.user,
            project=project,
            fields=json.dumps(serializer.validated_data["fields"], ensure_ascii=False),
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            worker.indices.add(index)

        worker.process()
