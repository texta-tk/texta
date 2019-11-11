import os
import json
import re
import sys

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.feedback import Feedback
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tagger.models import Tagger
from toolkit.tagger.tasks import train_tagger
from toolkit.core.project.models import Project
from toolkit.tagger.serializers import (
    TaggerSerializer,
    TaggerListFeaturesSerializer,
    TaggerTagTextSerializer,
    TaggerTagDocumentSerializer,
)
from toolkit.serializer_constants import (
    GeneralTextSerializer,
    FeedbackSerializer,
)
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.model_cache import ModelCache
from toolkit.embedding.views import global_phraser_cache
from toolkit.tools.text_processor import TextProcessor
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.core.task.models import Task
from toolkit.tools.mlp_analyzer import MLPAnalyzer
from toolkit.helper_functions import apply_celery_task
from toolkit.tagger.validators import validate_input_document
from toolkit.view_constants import (
    BulkDelete,
    ExportModel,
    FeedbackModelView,
)

# initialize model cache for taggers & phrasers
global_tagger_cache = ModelCache(TextTagger)
global_mlp_for_taggers = MLPAnalyzer()


class TaggerViewSet(viewsets.ModelViewSet, BulkDelete, ExportModel, FeedbackModelView):
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

    def perform_create(self, serializer):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']))

    def get_queryset(self):
        return Tagger.objects.filter(project=self.kwargs['project_pk'])

    def create(self, request, *args, **kwargs):
        serializer = TaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        # check if selected fields are present in the project:
        project_fields = set(Project.objects.get(id=self.kwargs['project_pk']).get_elastic_fields(path_list=True))
        entered_fields = set(serializer.validated_data['fields'])
        if not entered_fields.issubset(project_fields):
            return Response({'error': f'entered fields not in current project fields: {project_fields}'}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        try:
            model_location = json.loads(instance.location)['tagger']
            os.remove(model_location)
            os.remove(instance.plot.path)
            return Response({"success": "Tagger instance deleted, model and plot removed"}, status=status.HTTP_204_NO_CONTENT)
        except:
            return Response({"success": "Tagger instance deleted, but model and plot were was not removed"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], serializer_class=TaggerListFeaturesSerializer)
    def list_features(self, request, pk=None, project_pk=None):
        """Returns list of features for the tagger. By default, features are sorted by their relevance in descending order."""
        serializer = TaggerListFeaturesSerializer(data=request.data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve model
        tagger = global_tagger_cache.get_model(tagger_object)
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
        feature_info = {'features': features_to_show,
                        'total_features': len(selected_features),
                        'showing_features': len(features_to_show)}
        return Response(feature_info, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def stop_word_list(self, request, pk=None, project_pk=None):
        """Returns list of stop words for the Tagger."""
        # retrieve tagger object and load stop words
        tagger_object = self.get_object()
        success = {'stop_words': json.loads(tagger_object.stop_words)}
        return Response(success, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def stop_word_add(self, request, pk=None, project_pk=None):
        """Adds stop word to Tagger model."""
        serializer = GeneralTextSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        new_stop_word = serializer.validated_data['text']
        # retrieve tagger object and update stop word list
        tagger_object = self.get_object()
        stop_words = json.loads(tagger_object.stop_words)
        if new_stop_word not in stop_words:
            stop_words.append(new_stop_word)
        # save tagger object
        tagger_object.stop_words = json.dumps(stop_words)
        tagger_object.save()
        success = {'added': new_stop_word, 'stop_words': stop_words}
        return Response(success, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def stop_word_remove(self, request, pk=None, project_pk=None):
        """Removes stop word from Tagger model."""
        serializer = GeneralTextSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        remove_stop_word = serializer.validated_data['text']
        # retrieve tagger object and update stop word list
        tagger_object = self.get_object()
        stop_words = json.loads(tagger_object.stop_words)
        # check is word in list
        if remove_stop_word not in stop_words:
            return Response({'error': 'word not present among stop words'}, status=status.HTTP_400_BAD_REQUEST)
        # remove stop word
        stop_words.remove(remove_stop_word)
        # save tagger object
        tagger_object.stop_words = json.dumps(stop_words)
        tagger_object.save()
        success = {'removed': remove_stop_word, 'stop_words': stop_words}
        return Response(success, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the Tagger model."""
        instance = self.get_object()
        apply_celery_task(train_tagger, instance.pk)
        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=TaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """Returns list of tags for input text."""
        serializer = TaggerTagTextSerializer(data=request.data)
        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        # by default, lemmatizer is disabled
        lemmatizer = None
        # create lemmatizer if needed
        if serializer.validated_data['lemmatize'] == True:
            lemmatizer = global_mlp_for_taggers
            # check if lemmatizer available
            if not lemmatizer.status:
                return Response({'error': 'lemmatization failed. do you have MLP available?'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve tagger object
        tagger_object = self.get_object()
        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        # declare input_document variable
        input_document = serializer.validated_data['doc']
        # load field data
        tagger_field_data = json.loads(tagger_object.fields)
        # validate input document
        input_document, error_response = validate_input_document(input_document, tagger_field_data)
        if error_response:
            return error_response
        # by default, lemmatizer is disabled
        lemmatizer = False
        # lemmatize if needed
        if serializer.validated_data['lemmatize'] == True:
            lemmatizer = global_mlp_for_taggers
            # check if lemmatization available
            if not lemmatizer.status:
                return Response({'error': 'lemmatization failed. do you have MLP available?'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
        if not tagger_object.location:
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
        stop_words = json.loads(tagger_object.stop_words)
        # use phraser is embedding used
        if tagger_object.embedding:
            phraser = global_phraser_cache.get_model(tagger_object)
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
        # load model and 
        tagger = global_tagger_cache.get_model(tagger_object)
        # select function according to input type
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input, text_processor=text_processor)
        else:
            tagger_result = tagger.tag_text(tagger_input, text_processor=text_processor)
        # initial result
        prediction = {'result': bool(tagger_result[0]), 'probability': tagger_result[1]}
        # add optional feedback
        if feedback:
            project_pk = tagger_object.project.pk
            feedback_object = Feedback(project_pk, tagger_object.pk)
            feedback_id = feedback_object.store(tagger_input, prediction['result'])
            prediction['feedback'] = {'id': feedback_id}
        return prediction
