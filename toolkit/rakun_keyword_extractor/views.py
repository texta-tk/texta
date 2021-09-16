import json
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from toolkit.view_constants import BulkDelete
from .serializers import RakunExtractorSerializer, RakunExtractorRandomDocSerializer
import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from django.db import transaction
from toolkit.rakun_keyword_extractor.serializers import StopWordSerializer, RakunExtractorIndexSerializer
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.rakun_keyword_extractor.tasks import apply_rakun_extractor_to_index
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import GeneralTextSerializer
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.helper_functions import load_stop_words
from toolkit.settings import FACEBOOK_MODEL_SUFFIX
from toolkit.exceptions import SerializerNotValid


class RakunExtractorViewSet(viewsets.ModelViewSet, BulkDelete):
    serializer_class = RakunExtractorSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = ('id', 'author__username', 'description')

    def get_queryset(self):
        return RakunExtractor.objects.filter(project=self.kwargs['project_pk']).order_by('-id')

    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])

        rakun: RakunExtractor = serializer.save(
            author=self.request.user,
            project=project,
            stopwords=json.dumps(serializer.validated_data.get('stopwords', []), ensure_ascii=False)
        )

    @action(detail=True, methods=['post'], serializer_class=RakunExtractorIndexSerializer)
    def apply_to_index(self, request, pk=None, project_pk=None):
        with transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)

            rakun_object: RakunExtractor = self.get_object()
            rakun_object.task = Task.objects.create(rakunextractor=rakun_object, status=Task.STATUS_CREATED)
            rakun_object.save()

            project = Project.objects.get(pk=project_pk)
            indices = [index["name"] for index in serializer.validated_data["indices"]]

            fields = serializer.validated_data["fields"]
            query = serializer.validated_data["query"]
            bulk_size = serializer.validated_data["bulk_size"]
            es_timeout = serializer.validated_data["es_timeout"]

            fact_name = serializer.validated_data["new_fact_name"]
            fact_value = serializer.validated_data["new_fact_value"]

            add_spans = serializer.validated_data["add_spans"]

            args = (pk, indices, fields, query, bulk_size, es_timeout, fact_name, fact_value, add_spans)
            transaction.on_commit(lambda: apply_rakun_extractor_to_index.apply_async(args=args))

            message = "Started process of applying Rakun with id: {}".format(rakun_object.id)
            return Response({"message": message}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], serializer_class=StopWordSerializer)
    def stop_words(self, request, pk=None, project_pk=None):
        """Adds stop word to Rakun. Input should be a list of strings, e.g. ['word1', 'word2', 'word3']."""
        rakun_object = self.get_object()

        existing_stop_words = load_stop_words(rakun_object.stopwords)

        if self.request.method == 'GET':
            success = {'stopwords': existing_stop_words}
            return Response(success, status=status.HTTP_200_OK)

        elif self.request.method == 'POST':
            serializer = StopWordSerializer(data=request.data)

            # check if valid request
            if not serializer.is_valid():
                raise SerializerNotValid(detail=serializer.errors)

            new_stop_words = serializer.validated_data['stopwords']
            overwrite_existing = serializer.validated_data['overwrite_existing']

            if not overwrite_existing:
                # Add previous stopwords to the new ones
                new_stop_words += existing_stop_words

            # Remove duplicates
            new_stop_words = list(set(new_stop_words))

            # save rakun object
            rakun_object.stopwords = json.dumps(new_stop_words)
            rakun_object.save()

            return Response({"stopwords": new_stop_words}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=RakunExtractorSerializer)
    def duplicate(self, request, pk=None, project_pk=None):
        rakun_object: RakunExtractor = self.get_object()
        rakun_object.pk = None
        rakun_object.description = f"{rakun_object.description}_copy"
        rakun_object.author = self.request.user
        rakun_object.save()

        response = {
            "message": "Rakun extractor duplicated successfully!",
            "duplicate_id": rakun_object.pk
        }

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def extract_from_text(self, request, pk=None, project_pk=None):
        serializer = GeneralTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rakun_object: RakunExtractor = self.get_object()

        text = serializer.validated_data['text']

        keywords = rakun_object.get_rakun_keywords([text], field_path="", fact_name="rakun", fact_value="", add_spans=False)

        # apply rakun
        results = {
            "rakun_id": rakun_object.pk,
            "desscription": rakun_object.description,
            "result": True,
            "text": text,
            "keywords": keywords
        }
        return Response(results, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], serializer_class=RakunExtractorRandomDocSerializer)
    def extract_from_random_doc(self, request, pk=None, project_pk=None):
        """Returns prediction for a random document in Elasticsearch."""
        # get rakun object
        rakun_object: RakunExtractor = RakunExtractor.objects.get(pk=pk)

        serializer = RakunExtractorRandomDocSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project_object = Project.objects.get(pk=project_pk)
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        # retrieve rakun fields
        fields = serializer.validated_data["fields"]

        # retrieve random document
        random_doc = ElasticSearcher(indices=indices).random_documents(size=1)[0]
        flattened_doc = ElasticCore(check_connection=False).flatten(random_doc)

        # apply rakun
        results = {
            "rakun_id": rakun_object.pk,
            "description": rakun_object.description,
            "result": False,
            "keywords": [],
            "document": flattened_doc
        }
        final_keywords = []
        for field in fields:
            text = flattened_doc.get(field, None)
            results["document"][field] = text
            keywords = rakun_object.get_rakun_keywords([text], field_path=field, fact_name="rakun", fact_value="", add_spans=False)

            if keywords:
                final_keywords.extend(keywords)
                results["result"] = True

        results["keywords"] = final_keywords
        return Response(results, status=status.HTTP_200_OK)
