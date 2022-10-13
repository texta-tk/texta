import json
import os

import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.exceptions import NonExistantModelError, ProjectValidationFailed
from toolkit.filter_constants import FavoriteFilter
from toolkit.helper_functions import add_finite_url_to_feedback
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE
from toolkit.tagger.serializers import TaggerTagTextSerializer
from toolkit.torchtagger import choices
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.torchtagger.serializers import ApplyTaggerSerializer, EpochReportSerializer, TagRandomDocSerializer, TorchTaggerSerializer
from toolkit.torchtagger.tasks import apply_tagger, apply_tagger_to_index
from toolkit.view_constants import BulkDelete, FavoriteModelViewMixing, FeedbackModelView


class TorchTaggerFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('tasks__status', lookup_expr='icontains')


    class Meta:
        model = TorchTaggerObject
        fields = []


class TorchTaggerViewSet(viewsets.ModelViewSet, BulkDelete, FeedbackModelView, FavoriteModelViewMixing):
    serializer_class = TorchTaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectAccessInApplicationsAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TorchTaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score', 'precision', 'recall', 'tasks__status')


    def perform_create(self, serializer, **kwargs):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")

        tagger: TorchTaggerObject = serializer.save(
            author=self.request.user,
            project=project,
            fields=json.dumps(serializer.validated_data['fields']),
            **kwargs
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            tagger.indices.add(index)

        tagger.train()


    def get_queryset(self):
        return TorchTaggerObject.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    @action(detail=True, methods=['post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the TorchTagger model."""
        instance = self.get_object()
        instance.train()
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Returns list of tags for input text."""
        zip_name = f'torchtagger_model_{pk}.zip'

        tagger_object: TorchTaggerObject = self.get_object()
        data = tagger_object.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        tagger_id = TorchTaggerObject.import_resources(uploaded_file, request, project_pk)
        return Response({"id": tagger_id, "message": "Successfully imported model and associated files."}, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post', 'get'], serializer_class=EpochReportSerializer)
    def epoch_reports(self, request, pk=None, project_pk=None):
        """Retrieve epoch reports"""
        tagger_object: BertTaggerObject = self.get_object()

        if request.method == "GET":
            ignore_fields = choices.DEFAULT_REPORT_IGNORE_FIELDS
        else:
            serializer = EpochReportSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            ignore_fields = serializer.validated_data['ignore_fields']

        reports = json.loads(tagger_object.epoch_reports)
        filtered_reports = [{field: value for field, value in list(report.items()) if field not in ignore_fields} for report in reports]

        return Response(filtered_reports, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TagRandomDocSerializer)
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""

        # get tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.model:
            raise NonExistantModelError()

        serializer = TagRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = tagger_object.get_available_or_all_indices(indices)

        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)
        if not ElasticCore().check_if_indices_exist(indices):
            raise ProjectValidationFailed(detail=f'One or more index from {list(indices)} do not exist')

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]

        # filter out correct fields from the document
        random_doc_filtered = {k: v for k, v in random_doc.items() if k in tagger_fields}

        # apply tagger
        tagger_response = apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        serializer = TaggerTagTextSerializer(data=request.data)
        # check if valid request
        serializer.is_valid(raise_exception=True)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.model:
            raise NonExistantModelError()
        # apply tagger
        text = serializer.validated_data['text']
        feedback = serializer.validated_data['feedback_enabled']
        prediction = apply_tagger(tagger_object, text, feedback=feedback)
        prediction = add_finite_url_to_feedback(prediction, request)
        return Response(prediction, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ApplyTaggerSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        """Applt Torch tagger to an Elasticsearch index."""
        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            tagger_object = self.get_object()
            new_task = Task.objects.create(torchtagger=tagger_object, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY)
            tagger_object.save()

            tagger_object.tasks.add(new_task)

            indices = [index["name"] for index in serializer.validated_data["indices"]]
            # indices = project.get_available_or_all_project_indices(indices)

            fields = serializer.validated_data["fields"]
            fact_name = serializer.validated_data["new_fact_name"]
            fact_value = serializer.validated_data["new_fact_value"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]
            es_timeout = serializer.validated_data["es_timeout"]

            if tagger_object.fact_name:
                # Disable fact_value usage for multiclass taggers
                fact_value = ""

            args = (pk, indices, fields, fact_name, fact_value, query, bulk_size, max_chunk_bytes, es_timeout)
            transaction.on_commit(lambda: apply_tagger_to_index.apply_async(args=args, queue=CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying Torch Tagger with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)
