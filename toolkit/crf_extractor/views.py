import json

import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import CRFExtractor
from .serializers import CRFExtractorSerializer

#from toolkit.core.health.utils import get_redis_status
from toolkit.core.project.models import Project
#from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
#from toolkit.elastic.tools.core import ElasticCore
#from toolkit.elastic.tools.searcher import ElasticSearcher
#from toolkit.exceptions import NonExistantModelError, RedisNotAvailable, SerializerNotValid
#from toolkit.helper_functions import add_finite_url_to_feedback, load_stop_words
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
#from toolkit.serializer_constants import (
#    ProjectResourceImportModelSerializer)
#from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE
#from toolkit.tagger.models import Tagger
#from toolkit.tagger.serializers import (ApplyTaggerSerializer, StopWordSerializer, TagRandomDocSerializer, TaggerListFeaturesSerializer, TaggerMultiTagSerializer, TaggerSerializer, TaggerTagDocumentSerializer, TaggerTagTextSerializer)
#from toolkit.tagger.tasks import apply_tagger, apply_tagger_to_index, save_tagger_results, start_tagger_task, train_tagger_task
#from toolkit.tagger.validators import validate_input_document
from toolkit.view_constants import BulkDelete



class CRFExtractorFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')


    class Meta:
        model = CRFExtractor
        fields = []


class CRFExtractorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = CRFExtractorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = CRFExtractorFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


    def get_queryset(self):
        return CRFExtractor.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)
        serializer.validated_data.pop("indices")

        extractor: CRFExtractor = serializer.save(
            author=self.request.user,
            project=project,
            labels=json.dumps(serializer.validated_data['labels'])
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            extractor.indices.add(index)

        extractor.train()


    def destroy(self, request, *args, **kwargs):
        instance: CRFExtractor = self.get_object()
        instance.delete()
        return Response({"success": "CRFExtractor instance deleted, model and plot removed"}, status=status.HTTP_204_NO_CONTENT)
