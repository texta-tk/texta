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
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.embedding.phraser import Phraser
from toolkit.exceptions import MLPNotAvailable, NonExistantModelError, ProjectValidationFailed, SerializerNotValid
from toolkit.helper_functions import apply_celery_task
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.serializer_constants import (
    GeneralTextSerializer,
    ProjectResourceImportModelSerializer)
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import (TaggerListFeaturesSerializer, TaggerSerializer, TaggerTagDocumentSerializer, TaggerTagTextSerializer)
from toolkit.tagger.tasks import train_tagger
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tagger.validators import validate_input_document
from toolkit.tools.mlp_analyzer import MLPAnalyzer
from toolkit.tools.text_processor import TextProcessor
from toolkit.view_constants import (
    BulkDelete,
    FeedbackModelView,
)


# initialize model cache for taggers & phrasers
global_mlp_for_taggers = MLPAnalyzer()


class TaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')


    class Meta:
        model = Tagger
        fields = []


class TaggerViewSet(viewsets.ModelViewSet, BulkDelete, FeedbackModelView):
    """
    list:
    Returns list of Tagger objects.

    read:
    Return Tagger object by id.

    create:
    Creates Tagger object.

    update:
    Updates entire Tagger object.

    partial_update:
    Performs partial update on Tagger object.

    delete:
    Deletes Tagger object.
    """
    serializer_class = TaggerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


    def get_queryset(self):
        return Tagger.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer):
        tagger: Tagger = serializer.save(
            author=self.request.user,
            project=Project.objects.get(id=self.kwargs['project_pk']),
            fields=json.dumps(serializer.validated_data['fields'])
        )
        tagger.train()


    def perform_update(self, serializer):
        serializer.save(fields=json.dumps(serializer.validated_data['fields']))


    def destroy(self, request, *args, **kwargs):
        instance: Tagger = self.get_object()
        instance.delete()
        return Response({"success": "Tagger instance deleted, model and plot removed"}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['get'], serializer_class=TaggerListFeaturesSerializer)
    def list_features(self, request, pk=None, project_pk=None):
        """Returns list of features for the tagger. By default, features are sorted by their relevance in descending order."""
        serializer = TaggerListFeaturesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # retrieve tagger object
        tagger_object: Tagger = self.get_object()

        # check if tagger exists
        if not tagger_object.model.path:
            raise NonExistantModelError()

        # retrieve model
        tagger = TextTagger(tagger_object.id)
        tagger.load()

        try:
            # get feature names
            features = tagger.get_feature_names()
        except:
            return Response({'error': 'Error loading feature names. Are you using HashingVectorizer? It does not support feature names!'}, status=status.HTTP_400_BAD_REQUEST)

        feature_coefs = tagger.get_feature_coefs()
        supports = tagger.get_supports()
        selected_features = [feature for i, feature in enumerate(features) if supports[i]]
        selected_features = [{'feature': feature, 'coefficient': feature_coefs[i]} for i, feature in enumerate(selected_features) if feature_coefs[i] > 0]
        selected_features = sorted(selected_features, key=lambda k: k['coefficient'], reverse=True)

        features_to_show = selected_features[:serializer.validated_data['size']]
        feature_info = {
            'features': features_to_show,
            'total_features': len(selected_features),
            'showing_features': len(features_to_show)
        }
        return Response(feature_info, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'], serializer_class=GeneralTextSerializer)
    def stop_words(self, request, pk=None, project_pk=None):
        """Adds stop word to Tagger model. Input Text is a string of space separated words, eg 'word1 word2 word3'"""
        tagger_object = self.get_object()
        if self.request.method == 'GET':
            success = {'stop_words': tagger_object.stop_words}
            return Response(success, status=status.HTTP_200_OK)
        elif self.request.method == 'POST':
            serializer = GeneralTextSerializer(data=request.data)

            # check if valid request
            if not serializer.is_valid():
                raise SerializerNotValid(detail=serializer.errors)

            new_stop_words = serializer.validated_data['text']
            # save tagger object
            tagger_object.stop_words = new_stop_words
            tagger_object.save()

            return Response({"stop_words": new_stop_words}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the Tagger model."""
        instance = self.get_object()
        apply_celery_task(train_tagger, instance.pk)
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Returns list of tags for input text."""
        zip_name = f'tagger_model_{pk}.zip'

        tagger_object: Tagger = self.get_object()
        data = tagger_object.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        tagger_id = Tagger.import_resources(uploaded_file, request, project_pk)
        return Response({"id": tagger_id, "message": "Successfully imported model and associated files."}, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['post'], serializer_class=TaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """Returns list of tags for input text."""
        serializer = TaggerTagTextSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.model.path:
            raise NonExistantModelError()

        # by default, lemmatizer is disabled
        lemmatizer = None

        # create lemmatizer if needed
        if serializer.validated_data['lemmatize'] is True:
            lemmatizer = global_mlp_for_taggers

            # check if lemmatizer available
            if not lemmatizer.status:
                raise MLPNotAvailable(detail="Lemmatization failed. Check connection to MLP.")

        # apply tagger
        tagger_response = self.apply_tagger(
            tagger_object,
            serializer.validated_data['text'],
            input_type='text',
            lemmatizer=lemmatizer,
            feedback=serializer.validated_data['feedback_enabled']
        )
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TaggerTagDocumentSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """Returns list of tags for input document."""
        serializer = TaggerTagDocumentSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists

        if not tagger_object.model.path:
            raise NonExistantModelError()

        # declare input_document variable
        input_document = serializer.validated_data['doc']
        # load field data
        tagger_field_data = json.loads(tagger_object.fields)
        # validate input document
        input_document = validate_input_document(input_document, tagger_field_data)
        if isinstance(input_document, Exception):
            return input_document
        # by default, lemmatizer is disabled
        lemmatizer = False

        # lemmatize if needed
        if serializer.validated_data['lemmatize'] is True:
            lemmatizer = global_mlp_for_taggers

            # check if lemmatization available
            if not lemmatizer.status:
                raise MLPNotAvailable(detail="Lemmatization failed. Check connection to MLP.")

        # apply tagger
        tagger_response = self.apply_tagger(
            tagger_object,
            input_document,
            input_type='doc',
            lemmatizer=lemmatizer,
            feedback=serializer.validated_data['feedback_enabled'],
        )
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns list of tags for random document in Elasticsearch."""
        # get tagger object
        tagger_object = self.get_object()
        # check if tagger exists

        if not tagger_object.model.path:
            raise NonExistantModelError()

        if not tagger_object.model.path:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)
        if not ElasticCore().check_if_indices_exist(tagger_object.project.indices):
            return Response({'error': f'One or more index from {list(tagger_object.project.indices)} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve random document
        random_doc = ElasticSearcher(indices=tagger_object.project.indices).random_documents(size=1)[0]

        # filter out correct fields from the document
        random_doc_filtered = {k: v for k, v in random_doc.items() if k in tagger_fields}

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_object, tagger_input, input_type='text', phraser=None, lemmatizer=None, feedback=False):
        # create text processor object for tagger
        stop_words = tagger_object.stop_words.split(' ')
        # use phraser is embedding used
        if tagger_object.embedding:
            phraser = Phraser(tagger_object.id)
            phraser.load()

            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
        # load model and
        tagger = TextTagger(tagger_object.id)
        tagger.load()

        tagger.add_text_processor(text_processor)
        # select function according to input type
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        # initial result
        prediction = {'result': bool(tagger_result[0]), 'probability': tagger_result[1]}
        # add optional feedback
        if feedback:
            project_pk = tagger_object.project.pk
            feedback_object = Feedback(project_pk, tagger_object.pk)
            feedback_id = feedback_object.store(tagger_input, prediction['result'])
            prediction['feedback'] = {'id': feedback_id}
        return prediction
