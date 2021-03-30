import json
import os
import logging

import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.task.models import Task
from toolkit.core.project.models import Project

from toolkit.elastic.index.models import Index

from toolkit.exceptions import NonExistantModelError, ProjectValidationFailed, DownloadingModelsNotAllowedError, InvalidModelIdentifierError

from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE
from toolkit.evaluator.models import Evaluator as EvaluatorObject
from toolkit.evaluator.serializers import EvaluatorSerializer, IndividualResultsSerializer, FilteredAverageSerializer
from toolkit.evaluator.tasks import evaluate_tags_task, filter_results, filter_and_average_results
from toolkit.evaluator import choices

from toolkit.view_constants import BulkDelete

from collections import OrderedDict

class EvaluatorFilter(filters.FilterSet):
    description = filters.CharFilter("description", lookup_expr="icontains")
    task_status = filters.CharFilter("task__status", lookup_expr="icontains")


    class Meta:
        model = EvaluatorObject
        fields = []


class EvaluatorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = EvaluatorSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = EvaluatorFilter
    ordering_fields = ("id", "author__username", "description",  "task__time_started", "task__time_completed", "f1_score", "precision", "recall", "task__status")


    def get_queryset(self):
        return EvaluatorObject.objects.filter(project=self.kwargs["project_pk"]).order_by("-id")


    def perform_create(self, serializer, **kwargs):
        project = Project.objects.get(id=self.kwargs["project_pk"])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        es_timeout = serializer.validated_data["es_timeout"]
        scroll_size = serializer.validated_data["scroll_size"]

        serializer.validated_data.pop("indices")

        evaluator: EvaluatorObject = serializer.save(
            author=self.request.user,
            project=project,
            **kwargs
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            evaluator.indices.add(index)

        query = json.loads(serializer.validated_data["query"])

        new_task = Task.objects.create(evaluator=evaluator, status="created")
        evaluator.task = new_task
        evaluator.save()

        evaluate_tags_task.apply_async(args=(evaluator.pk, indices, query, es_timeout, scroll_size), queue=CELERY_LONG_TERM_TASK_QUEUE)


    def destroy(self, request, *args, **kwargs):
        evaluator_object: Evaluator = self.get_object()
        evaluator_object.delete()
        return Response({"success": "Evaluator instance deleted, plot file removed"}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=["get", "post"], serializer_class = FilteredAverageSerializer)
    def filtered_average(self, request, pk=None, project_pk=None):
        """Return average scores of (optionally filtered) individual results."""
        evaluator_object: EvaluatorObject = self.get_object()
        if evaluator_object.evaluation_type in ["binary"]:
            return Response("This operation is enabled only for multilabel evaluators.", status=status.HTTP_405_METHOD_NOT_ALLOWED)

        binary_results = json.loads(evaluator_object.individual_results)

        if request.method == "GET":
            max_count = choices.DEFAULT_MAX_COUNT
            min_count = choices.DEFAULT_MIN_COUNT
            metric_restrictions = {}
        else:
            serializer = FilteredAverageSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            max_count = serializer.validated_data["max_count"]
            min_count = serializer.validated_data["min_count"]
            metric_restrictions = serializer.validated_data["metric_restrictions"]
            if not metric_restrictions:
                metric_restrictions = {}

        if binary_results:
            avg_scores = filter_and_average_results(binary_results, min_count=min_count, max_count=max_count, metric_restrictions=metric_restrictions)
        else:
            avg_scores = {}

        return Response(avg_scores, status=status.HTTP_200_OK)


    @action(detail=True, methods=["post"], serializer_class = IndividualResultsSerializer)
    def individual_results(self, request, pk=None, project_pk=None):
        """Retrieve individual scores for multilabel tags."""
        evaluator_object: EvaluatorObject = self.get_object()

        if evaluator_object.evaluation_type in ["binary"]:
            return Response("This operation is applicable only for multilabel evaluators.", status=status.HTTP_405_METHOD_NOT_ALLOWED)

        binary_results = json.loads(evaluator_object.individual_results)

        serializer = IndividualResultsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        max_count = serializer.validated_data["max_count"]
        min_count = serializer.validated_data["min_count"]
        order_by = serializer.validated_data["order_by"]
        order_desc = serializer.validated_data["order_desc"]
        metric_restrictions = serializer.validated_data["metric_restrictions"]


        if not metric_restrictions:
            metric_restrictions = {}

        if isinstance(metric_restrictions, str):
            metric_restrictions = json.loads(metric_restrictions)

        filtered_results = filter_results(binary_results, min_count=min_count, max_count=max_count, metric_restrictions=metric_restrictions)

        if order_by == "alphabetic":
            filtered_results = OrderedDict(sorted(filtered_results.items(), key=lambda x: x[0], reverse=order_desc))

        else:
            filtered_results = OrderedDict(sorted(filtered_results.items(), key=lambda x: x[1][order_by], reverse=order_desc))

        filtered_bin_results = {"total": len(filtered_results), "filtered_results": filtered_results}

        return Response(filtered_bin_results, status=status.HTTP_200_OK)


    @action(detail=True, methods=["get"])
    def export_model(self, request, pk=None, project_pk=None):
        zip_name = f"evaluator_model_{pk}.zip"

        tagger_object: EvaluatorObject = self.get_object()
        data = tagger_object.export_resources()
        response = HttpResponse(data)
        response["Content-Disposition"] = "attachment; filename=" + os.path.basename(zip_name)
        return response


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        tagger_id = EvaluatorObject.import_resources(uploaded_file, request, project_pk)
        return Response({"id": tagger_id, "message": "Successfully imported model and associated files."}, status=status.HTTP_201_CREATED)
