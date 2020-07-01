import json
import os

import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.models import Index
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.embedding.phraser import Phraser
from toolkit.exceptions import NonExistantModelError, ProjectValidationFailed
from toolkit.helper_functions import add_finite_url_to_feedback
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE
from toolkit.tagger.serializers import TaggerTagTextSerializer
from toolkit.tools.text_processor import TextProcessor
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.torchtagger.serializers import TagRandomDocSerializer, TorchTaggerSerializer
from toolkit.torchtagger.tasks import train_torchtagger
from toolkit.torchtagger.torchtagger import TorchTagger
from toolkit.view_constants import BulkDelete, FeedbackModelView


class TorchTaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')


    class Meta:
        model = TorchTaggerObject
        fields = []


class TorchTaggerViewSet(viewsets.ModelViewSet, BulkDelete, FeedbackModelView):
    serializer_class = TorchTaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TorchTaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


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
        return TorchTaggerObject.objects.filter(project=self.kwargs['project_pk'])


    @action(detail=True, methods=['post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the TorchTagger model."""
        instance = self.get_object()
        train_torchtagger.apply_async(args=(instance.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)
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


    @action(detail=True, methods=['post'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""

        # get tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.model:
            raise NonExistantModelError()

        serializer = TagRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_object = Project.objects.get(pk=project_pk)
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)
        if not ElasticCore().check_if_indices_exist(tagger_object.project.get_indices()):
            raise ProjectValidationFailed(detail=f'One or more index from {list(tagger_object.project.get_indices())} do not exist')

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]

        # filter out correct fields from the document
        random_doc_filtered = {k: v for k, v in random_doc.items() if k in tagger_fields}

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
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
        prediction = self.apply_tagger(tagger_object, text, feedback=feedback)
        prediction = add_finite_url_to_feedback(prediction, request)
        return Response(prediction, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_object, tagger_input, input_type='text', lemmatize=None, feedback=False):
        # use phraser is embedding used
        if tagger_object.embedding:
            phraser = Phraser(tagger_object.embedding.id)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, lemmatize=lemmatize)
        else:
            text_processor = TextProcessor(remove_stop_words=True, lemmatize=lemmatize)
        # retrieve model
        tagger = TorchTagger(tagger_object.id)
        tagger.load()
        # tag text
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        prediction = {'result': tagger_result[0], 'probability': tagger_result[1]}
        # add optional feedback
        if feedback:
            project_pk = tagger_object.project.pk
            feedback_object = Feedback(project_pk, model_object=tagger_object)
            feedback_id = feedback_object.store(tagger_input, prediction['result'])
            feedback_url = f'/projects/{project_pk}/torchtaggers/{tagger_object.pk}/feedback/'
            prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}
        return prediction
