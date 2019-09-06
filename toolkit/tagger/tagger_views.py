import json
import re
import sys

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tagger.models import Tagger
from toolkit.tagger.tasks import train_tagger
from toolkit.core.project.models import Project
from toolkit.tagger.serializers import TaggerSerializer, FeatureListSerializer, \
                                       TextSerializer, DocSerializer
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.model_cache import ModelCache
from toolkit.embedding.views import phraser_cache
from toolkit.tools.text_processor import TextProcessor
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.core.task.models import Task
from toolkit.tools.mlp_lemmatizer import MLPLemmatizer
from toolkit.helper_functions import apply_celery_task, get_payload
from toolkit.tagger.validators import validate_input_document

# initialize model cache for taggers & phrasers
tagger_cache = ModelCache(TextTagger)


class TaggerViewSet(viewsets.ModelViewSet):
    serializer_class = TaggerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
        )

    def perform_create(self, serializer):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']),
                        query=json.dumps(serializer.validated_data['query']))


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



    @action(detail=True, methods=['get', 'post'], serializer_class=FeatureListSerializer)
    def list_features(self, request, pk=None, project_pk=None):
        """
        API endpoint for listing tagger features.
        """
        data = get_payload(request)
        serializer = FeatureListSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve model
        tagger = tagger_cache.get_model(tagger_object.pk)

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


    @action(detail=True, methods=['get', 'post'])
    def stop_word_list(self, request, pk=None, project_pk=None):
        """
        API endpoint for listing tagger object stop words.
        """
        # retrieve tagger object and load stop words
        tagger_object = self.get_object()
        success = {'stop_words': json.loads(tagger_object.stop_words)}
        return Response(success, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'], serializer_class=TextSerializer)
    def stop_word_add(self, request, pk=None, project_pk=None):
        """
        API endpoint for adding a new stop word to tagger
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

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


    @action(detail=True, methods=['get', 'post'], serializer_class=TextSerializer)
    def stop_word_remove(self, request, pk=None, project_pk=None):
        """
        API endpoint for removing tagger stop word.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

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


    @action(detail=True, methods=['get', 'post'])
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """
        API endpoint for retraining tagger model.
        """
        instance = self.get_object()
        
        apply_celery_task(train_tagger, instance.pk)

        return Response({'success': 'retraining task created'}, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=TextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging raw text.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

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
            lemmatizer = MLPLemmatizer(lite=True)
            # check if lemmatizer available
            if not lemmatizer.status:
                return Response({'error': 'lemmatization failed. do you have MLP available?'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, serializer.validated_data['text'], input_type='text', lemmatizer=lemmatizer)
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=DocSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging JSON documents.
        """
        data = get_payload(request)
        serializer = DocSerializer(data=data)

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
            lemmatizer = MLPLemmatizer(lite=True)
            # check if lemmatization available
            if not lemmatizer.status:
                return Response({'error': 'lemmatization failed. do you have MLP available?'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, input_document, input_type='doc', lemmatizer=lemmatizer)
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """
        API endpoint for tagging a random document.
        """
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
        random_doc_filtered = {k:v for k,v in random_doc.items() if k in tagger_fields}
        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_object, tagger_input, input_type='text', phraser=None, lemmatizer=None):
        # create text processor object for tagger
        stop_words = json.loads(tagger_object.stop_words)

        if tagger_object.embedding:
            phraser = phraser_cache.get_model(tagger_object.embedding.pk)
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)

        tagger = tagger_cache.get_model(tagger_object.id)
        tagger.add_text_processor(text_processor)

        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        return {'result': bool(tagger_result[0]), 'probability': tagger_result[1]}
