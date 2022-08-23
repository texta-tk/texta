import json
import rest_framework.filters as drf_filters
from django.db import transaction
from django_filters import rest_framework as filters
from rest_framework import permissions, viewsets
from rest_framework.views import APIView
from rest_framework.renderers import BrowsableAPIRenderer, HTMLFormRenderer, JSONRenderer
from rest_framework.response import Response
from toolkit.elastic.index.models import Index
from .serializers import SummarizerIndexSerializer, SummarizerSummarizeSerializer
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from .models import Summarizer
from toolkit.view_constants import BulkDelete
from .sumy import Sumy
from toolkit.core.project.models import Project


class SummarizerIndexViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = SummarizerIndexSerializer
    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = (
    'id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score',
    'precision', 'recall', 'tasks__status')
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    def get_queryset(self):
        return Summarizer.objects.filter(project=self.kwargs['project_pk']).order_by('-id')

    def perform_create(self, serializer):
        with transaction.atomic():
            project = Project.objects.get(id=self.kwargs['project_pk'])
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)
            serializer.validated_data.pop("indices")
            # summarize text
            worker: Summarizer = serializer.save(
                    author=self.request.user,
                    project=project,
                    fields=json.dumps(serializer.validated_data["fields"]),
                    algorithm=list(serializer.validated_data["algorithm"]),
                )
            for index in Index.objects.filter(name__in=indices, is_open=True):
                worker.indices.add(index)
            worker.process()


class SummarizerSummarize(APIView):
    serializer_class = SummarizerSummarizeSerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = SummarizerSummarizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = serializer.validated_data["text"]
        algorithm = list(serializer.validated_data["algorithm"])
        ratio = serializer.validated_data["ratio"]

        sumy = Sumy()

        results = sumy.run_on_tokenized(text=text, summarizer_names=algorithm, ratio=ratio)

        return Response(results)
