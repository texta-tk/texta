from celery import group
import json
import os
import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from texta_tagger.tagger import Tagger as TextTagger

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.models import Index
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.exceptions import NonExistantModelError, RedisNotAvailable, SerializerNotValid
from toolkit.helper_functions import add_finite_url_to_feedback
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.serializer_constants import (
    GeneralTextSerializer,
    ProjectResourceImportModelSerializer)
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import (
    TagRandomDocSerializer,
    TaggerListFeaturesSerializer,
    TaggerSerializer,
    TaggerTagDocumentSerializer,
    TaggerTagTextSerializer,
    TaggerMultiTagSerializer,
    ApplyTaggerSerializer
    )
from toolkit.tagger.tasks import apply_tagger, save_tagger_results, start_tagger_task, train_tagger_task
from toolkit.tagger.validators import validate_input_document
from toolkit.view_constants import (
    BulkDelete,
    FeedbackModelView,
)
from toolkit.tools.lemmatizer import CeleryLemmatizer
from toolkit.core.health.utils import get_redis_status


class TaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')


    class Meta:
        model = Tagger
        fields = []


class TaggerViewSet(viewsets.ModelViewSet, BulkDelete, FeedbackModelView):
    serializer_class = TaggerSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'f1_score', 'precision', 'recall', 'task__status')


    def get_queryset(self):
        return Tagger.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        serializer.validated_data.pop("indices")

        tagger: Tagger = serializer.save(
            author=self.request.user,
            project=project,
            fields=json.dumps(serializer.validated_data['fields'])
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            tagger.indices.add(index)

        tagger.train()


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
        tagger = TextTagger()
        tagger.load_django(tagger_object)
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
        chain = start_tagger_task.s() | train_tagger_task.s() | save_tagger_results.s()
        transaction.on_commit(lambda: chain.apply_async(args=(instance.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE))

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
        # apply tagger
        tagger_response = apply_tagger(
            tagger_object.id,
            serializer.validated_data['text'],
            input_type='text',
            lemmatize=serializer.validated_data['lemmatize'],
            feedback=serializer.validated_data['feedback_enabled']
        )
        # if feedback was enabled, add url
        tagger_response = add_finite_url_to_feedback(tagger_response, request)
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
        # apply tagger
        tagger_response = apply_tagger(
            tagger_object.id,
            input_document,
            input_type='doc',
            lemmatize=serializer.validated_data['lemmatize'],
            feedback=serializer.validated_data['feedback_enabled'],
        )
        # if feedback was enabled, add url
        tagger_response = add_finite_url_to_feedback(tagger_response, request)
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""
        # get tagger object
        tagger_object = self.get_object()
        # check if tagger exists

        if not tagger_object.model.path:
            raise NonExistantModelError()

        if not tagger_object.model.path:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TagRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_object = Project.objects.get(pk=project_pk)
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)
        if not ElasticCore().check_if_indices_exist(tagger_object.project.get_indices()):
            return Response({'error': f'One or more index from {list(tagger_object.project.get_indices())} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]

        # filter out correct fields from the document
        random_doc_filtered = {k: v for k, v in random_doc.items() if k in tagger_fields}

        # apply tagger
        tagger_response = apply_tagger(tagger_object.id, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)


    @action(detail=False, methods=['post'], serializer_class=TaggerMultiTagSerializer)
    def multitag_text(self, request, pk=None, project_pk=None):
        """
        Applies list of tagger objects inside project to any text.
        This is different from Tagger Group as **all** taggers in project are used and they do not have to reside in the same Tagger Group.
        Returns list of tags.
        """
        serializer = TaggerMultiTagSerializer(data=request.data)
        # validate serializer
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        # get project object
        project_object = Project.objects.get(pk=project_pk)
        # get available taggers from project
        taggers = Tagger.objects.filter(project=project_object).filter(task__status=Task.STATUS_COMPLETED)
        # filter again
        if serializer.validated_data['taggers']:
            taggers = taggers.filter(pk__in=serializer.validated_data['taggers'])
        # error if filtering resulted 0 taggers
        if not taggers:
            raise NonExistantModelError(detail='No tagging models available.')
        # retrieve params
        lemmatize = serializer.validated_data['lemmatize']
        feedback = serializer.validated_data['feedback_enabled']
        text = serializer.validated_data['text']
        hide_false = serializer.validated_data['hide_false']
        # error if redis not available
        if not get_redis_status()['alive']:
            raise RedisNotAvailable()
        # lemmatize text just once before giving it to taggers!
        if lemmatize:
            text = CeleryLemmatizer().lemmatize(text)
        # tag text using celery group primitive
        group_task = group(apply_tagger.s(tagger.pk, text, input_type='text', lemmatize=False, feedback=feedback) for tagger in taggers)
        group_results = [a for a in group_task.apply(queue=CELERY_SHORT_TERM_TASK_QUEUE).get() if a]
        # remove non-hits
        if hide_false is True:
            group_results = [a for a in group_results if a['result']]
        # if feedback was enabled, add urls
        group_results = [add_finite_url_to_feedback(a, request) for a in group_results]
        # sort & return tags
        sorted_tags = sorted(group_results, key=lambda k: k['probability'], reverse=True)
        return Response(sorted_tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ApplyTaggerSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        from toolkit.tagger.tasks import apply_tagger_to_index

        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            tagger_object = self.get_object()
            tagger_object.task = Task.objects.create(tagger=tagger_object, status=Task.STATUS_CREATED)
            tagger_object.save()

            project = Project.objects.get(pk=project_pk)
            indices = [index["name"] for index in serializer.validated_data["indices"]]
            indices = project.get_available_or_all_project_indices(indices)

            fields = serializer.validated_data["fields"]
            fact_name = serializer.validated_data["new_fact_name"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]

            args = (pk, indices, fields, fact_name, query, bulk_size, max_chunk_bytes)
            transaction.on_commit(lambda: apply_tagger_to_index.apply_async(args=args, queue=CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying Tagger with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_200_OK)
