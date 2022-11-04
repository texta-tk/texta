import json
import os

import rest_framework.filters as drf_filters
from celery import group
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher
from texta_tagger.tagger import Tagger as TextTagger

from toolkit.core.health.utils import get_redis_status
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.exceptions import NonExistantModelError, RedisNotAvailable, SerializerNotValid
from toolkit.filter_constants import FavoriteFilter
from toolkit.helper_functions import add_finite_url_to_feedback, load_stop_words, minio_connection
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import ProjectResourceImportModelSerializer, EmptySerializer, S3DownloadSerializer, S3UploadSerializer
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import (ApplyTaggerSerializer, StopWordSerializer, TagRandomDocSerializer, TaggerListFeaturesSerializer,
                                        TaggerMultiTagSerializer, TaggerSerializer,
                                        TaggerTagDocumentSerializer, TaggerTagTextSerializer)
from toolkit.tagger.tasks import apply_tagger, apply_tagger_to_index, upload_tagger_files, download_tagger_model
from toolkit.tagger.validators import validate_input_document
from toolkit.tools.lemmatizer import CeleryLemmatizer
from toolkit.view_constants import (
    BulkDelete,
    FavoriteModelViewMixing, FeedbackModelView,
)


class TaggerFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')
    tg_description = filters.CharFilter('taggergroup__description', lookup_expr='icontains')
    task_status = filters.CharFilter('tasks__status', lookup_expr='icontains')
    is_favorited = filters.BooleanFilter(field_name="favorited_users", method="get_is_favorited")

    def get_is_favorited(self, queryset, name, value):
        if value is True:
            return queryset.filter(favorited_users__username=self.request.user.username)
        else:
            return queryset.filter(~Q(favorited_users__username=self.request.user.username))

    class Meta:
        model = Tagger
        fields = []


class TaggerViewSet(viewsets.ModelViewSet, BulkDelete, FeedbackModelView, FavoriteModelViewMixing):
    serializer_class = TaggerSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = TaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'f1_score', 'precision', 'recall', 'tasks__status')

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
            fields=json.dumps(serializer.validated_data['fields']),
            stop_words=json.dumps(serializer.validated_data.get('stop_words', []), ensure_ascii=False)
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            tagger.indices.add(index)

        tagger.train()

    def destroy(self, request, *args, **kwargs):
        instance: Tagger = self.get_object()
        instance.delete()
        return Response({"success": "Tagger instance deleted, model and plot removed"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get', 'post'], serializer_class=TaggerListFeaturesSerializer)
    def list_features(self, request, pk=None, project_pk=None):
        """Returns list of features for the tagger. By default, features are sorted by their relevance in descending order."""

        if self.request.method == 'GET':
            serializer = TaggerListFeaturesSerializer(data=request.query_params)

        elif self.request.method == 'POST':
            serializer = TaggerListFeaturesSerializer(data=request.data)

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

        serializer.is_valid(raise_exception=True)
        size = serializer.validated_data['size']
        features_to_show = selected_features[:size]

        feature_info = {
            'total_features': len(selected_features),
            'showing_features': len(features_to_show),
            'features': features_to_show
        }
        return Response(feature_info, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get', 'post'], serializer_class=StopWordSerializer)
    def stop_words(self, request, pk=None, project_pk=None):
        """Adds stop word to Tagger model. Input should be a list of strings, e.g. ['word1', 'word2', 'word3']."""
        tagger_object = self.get_object()

        existing_stop_words = load_stop_words(tagger_object.stop_words)

        if self.request.method == 'GET':
            success = {'stop_words': existing_stop_words}
            return Response(success, status=status.HTTP_200_OK)

        elif self.request.method == 'POST':
            serializer = StopWordSerializer(data=request.data)

            # check if valid request
            if not serializer.is_valid():
                raise SerializerNotValid(detail=serializer.errors)

            new_stop_words = serializer.validated_data['stop_words']
            overwrite_existing = serializer.validated_data['overwrite_existing']
            ignore_numbers = serializer.validated_data['ignore_numbers']

            if not overwrite_existing:
                # Add previous stopwords to the new ones
                new_stop_words += existing_stop_words

            # Remove duplicates
            new_stop_words = list(set(new_stop_words))

            # save tagger object
            tagger_object.stop_words = json.dumps(new_stop_words)
            tagger_object.ignore_numbers = ignore_numbers
            tagger_object.save()

            return Response({"stop_words": new_stop_words, "ignore_numbers": ignore_numbers}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=EmptySerializer)
    def retrain_tagger(self, request, pk=None, project_pk=None):
        """Starts retraining task for the Tagger model."""
        instance = self.get_object()
        instance.train()
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
        tagger_id = Tagger.import_resources(uploaded_file, request.user.pk, project_pk)
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

    @action(detail=True, methods=['post'], serializer_class=EmptySerializer)
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

        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = tagger_object.get_available_or_all_indices(indices)

        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)

        if not indices:
            raise ValidationError("No indexes have been added to the Tagger and Project!")

        if not ElasticCore().check_if_indices_exist(indices):
            return Response({'error': f'One or more index from {list(indices)} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

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
        taggers = Tagger.objects.filter(project=project_object, tasks__status=Task.STATUS_COMPLETED)
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
        group_results = [a for a in group_task.apply(queue=settings.CELERY_SHORT_TERM_TASK_QUEUE).get() if a]
        # remove non-hits
        if hide_false is True:
            group_results = [a for a in group_results if a['result']]
        # if feedback was enabled, add urls
        group_results = [add_finite_url_to_feedback(a, request) for a in group_results]
        # sort & return tags
        sorted_tags = sorted(group_results, key=lambda k: k['probability'], reverse=True)
        return Response(sorted_tags, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=S3UploadSerializer)
    @minio_connection
    def upload_into_s3(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minio_path = serializer.validated_data["minio_path"]
        tagger = self.get_object()
        task = Task.objects.create(tagger=tagger, status=Task.STATUS_QUEUED, task_type=Task.TYPE_UPLOAD)
        tagger.tasks.add(task)
        transaction.on_commit(lambda: upload_tagger_files.apply_async(args=(tagger.pk, minio_path), queue=settings.CELERY_LONG_TERM_TASK_QUEUE))
        return Response({"message": "Started task for uploading model into S3!"})

    @action(detail=False, methods=['post'], serializer_class=S3DownloadSerializer)
    @minio_connection
    def download_from_s3(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        minio_path = serializer.validated_data["minio_path"]
        version_id = serializer.validated_data["version_id"]

        transaction.on_commit(lambda: download_tagger_model.apply_async(args=(minio_path, request.user.pk, project_pk, version_id), queue=settings.CELERY_LONG_TERM_TASK_QUEUE))

        return Response({"message": "Started task for downloading model from S3!"})

    @action(detail=True, methods=['post'], serializer_class=ApplyTaggerSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        """Apply tagger to an Elasticsearch index."""
        with transaction.atomic():
            # We're pulling the serializer with the function bc otherwise it will not
            # fetch the context for whatever reason.
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            tagger_object = self.get_object()
            tagger_object.tasks.add(Task.objects.create(tagger=tagger_object, status=Task.STATUS_CREATED, task_type=Task.TYPE_APPLY))

            indices = [index["name"] for index in serializer.validated_data["indices"]]

            fields = serializer.validated_data["fields"]
            fact_name = serializer.validated_data["new_fact_name"]
            fact_value = serializer.validated_data["new_fact_value"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            max_chunk_bytes = serializer.validated_data["max_chunk_bytes"]
            es_timeout = serializer.validated_data["es_timeout"]
            lemmatize = serializer.validated_data["lemmatize"]

            if tagger_object.fact_name:
                # Disable fact_value usage for multiclass taggers
                fact_value = ""

            object_args = {"lemmatize": lemmatize}

            object_type = "tagger"

            args = (pk, indices, fields, fact_name, fact_value, query, bulk_size, max_chunk_bytes, es_timeout, object_type, object_args)
            transaction.on_commit(lambda: apply_tagger_to_index.apply_async(args=args, queue=settings.CELERY_LONG_TERM_TASK_QUEUE))

            message = "Started process of applying Tagger with id: {}".format(tagger_object.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)
