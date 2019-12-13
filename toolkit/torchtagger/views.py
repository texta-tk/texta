import os
import json
import numpy as np

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject
from toolkit.torchtagger.torchtagger import TorchTagger
from toolkit.core.project.models import Project
from toolkit.exceptions import ProjectValidationFailed
from toolkit.torchtagger.serializers import TorchTaggerSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete, ExportModel, FeedbackModelView
from toolkit.tagger.serializers import TaggerTagTextSerializer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.text_processor import TextProcessor
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.feedback import Feedback
from toolkit.helper_functions import apply_celery_task
from toolkit.torchtagger.tasks import train_torchtagger

from django_filters import rest_framework as filters
import rest_framework.filters as drf_filters


class TorchTaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')

    class Meta:
        model = TorchTaggerObject
        fields = []


# forbid PUT/PATCH?
class TorchTaggerViewSet(viewsets.ModelViewSet, BulkDelete, ExportModel, FeedbackModelView):
    serializer_class = TorchTaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
        )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TorchTaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


    def perform_create(self, serializer, **kwargs):
        tagger: TorchTagger = serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']),
                        **kwargs)
        tagger.train()


    def get_queryset(self):
        return TorchTaggerObject.objects.filter(project=self.kwargs['project_pk'])


    @action(detail=True, methods=['post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the TorchTagger model."""
        instance = self.get_object()
        apply_celery_task(train_torchtagger, instance.pk)
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""
        # get tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.model:
            raise NonExistantModelError()
        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)
        if not ElasticCore().check_if_indices_exist(tagger_object.project.indices):
            raise ProjectValidationFailed(detail=f'One or more index from {list(tagger_object.project.indices)} do not exist')
        # retrieve random document
        random_doc = ElasticSearcher(indices=tagger_object.project.indices).random_documents(size=1)[0]
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
        return Response(prediction, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_object, tagger_input, input_type='text', lemmatizer=None, feedback=False):
        # use phraser is embedding used
        if tagger_object.embedding:
            phraser = Phraser(tagger_object.embedding.id)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, lemmatizer=lemmatizer)
        else:
            text_processor = TextProcessor(remove_stop_words=True, lemmatizer=lemmatizer)
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
            prediction['feedback'] = {'id': feedback_id}
        return prediction
