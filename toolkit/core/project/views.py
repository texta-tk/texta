import json
import pathlib

import elasticsearch
import elasticsearch_dsl
import rest_framework.filters as drf_filters
from celery import group
from django.db.models import Count
from django.urls import reverse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from toolkit.core.health.utils import get_redis_status
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import (
    ExportSearcherResultsSerializer, ProjectGetFactsSerializer,
    ProjectGetSpamSerializer,
    ProjectMultiTagSerializer,
    ProjectSearchByQuerySerializer,
    ProjectSerializer,
    ProjectSimplifiedSearchSerializer,
    ProjectSuggestFactNamesSerializer,
    ProjectSuggestFactValuesSerializer
)
from toolkit.core.task.models import Task
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.query import Query
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.serializers import ElasticScrollSerializer
from toolkit.elastic.spam_detector import SpamDetector
from toolkit.exceptions import NonExistantModelError, ProjectValidationFailed, RedisNotAvailable, SerializerNotValid
from toolkit.helper_functions import add_finite_url_to_feedback, hash_string
from toolkit.permissions.project_permissions import (ExtraActionResource, IsSuperUser, ProjectAllowed)
from toolkit.settings import CELERY_SHORT_TERM_TASK_QUEUE, RELATIVE_PROJECT_DATA_PATH, SEARCHER_FOLDER_KEY
from toolkit.tagger.models import Tagger
from toolkit.tagger.tasks import apply_tagger
from toolkit.tools.autocomplete import Autocomplete
from toolkit.view_constants import FeedbackIndexView


class ProjectFilter(filters.FilterSet):
    title = filters.CharFilter('title', lookup_expr='icontains')


    class Meta:
        model = Project
        fields = []


class ProjectViewSet(viewsets.ModelViewSet, FeedbackIndexView):
    pagination_class = None
    serializer_class = ProjectSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = ProjectFilter
    ordering_fields = ('id', 'title', 'users_count', 'indices_count',)


    def get_permissions(self):
        """
        Disable project creation for non-superusers
        """
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, IsSuperUser]
        else:
            permission_classes = self.permission_classes
        return [permission() for permission in permission_classes]


    def get_queryset(self):
        queryset = Project.objects.annotate(users_count=Count('users'), indices_count=Count('indices')).all()
        current_user = self.request.user
        if not current_user.is_superuser:
            return queryset.filter(users=current_user)
        return queryset


    @action(detail=True, methods=["post"], serializer_class=ExportSearcherResultsSerializer, permission_classes=[IsAuthenticated, ExtraActionResource])
    def export_search(self, request, pk=None, project_pk=None):
        try:
            serializer: ExportSearcherResultsSerializer = self.get_serializer(data=request.data)
            model: Project = self.get_object()
            serializer.is_valid(raise_exception=True)

            # Use the query as a hash to avoid creating duplicate files.
            query = serializer.validated_data["query"]
            query_str = json.dumps(query, sort_keys=True, ensure_ascii=False)

            indices = model.get_available_or_all_project_indices(serializer.validated_data["indices"])
            indices = ",".join(indices)

            original_query = elasticsearch_dsl.Search().from_dict(query)
            with_es = original_query.using(ElasticCore().es)
            index_limitation = with_es.index(indices)
            limit_by_n_docs = index_limitation.extra(size=10000)

            path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(pk) / SEARCHER_FOLDER_KEY
            path.mkdir(parents=True, exist_ok=True)
            file_name = f"{hash_string(query_str)}.jl"

            with open(path / file_name, "w+", encoding="utf8") as fp:
                for item in limit_by_n_docs.scan():
                    item = item.to_dict()
                    json_string = json.dumps(item, ensure_ascii=False)
                    fp.write(f"{json_string}\n")

            url = reverse("protected_serve", kwargs={"project_id": int(pk), "application": SEARCHER_FOLDER_KEY, "file_name": file_name})
            return Response(request.build_absolute_uri(url))

        except elasticsearch.exceptions.RequestError:
            return Response({"detail": "Could not parse the query you sent!"}, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, methods=["post"], serializer_class=ElasticScrollSerializer, permission_classes=[IsAuthenticated, ExtraActionResource])
    def scroll(self, request, pk=None, project_pk=None):
        serializer = ElasticScrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        indices = serializer.validated_data["indices"]
        scroll_id = serializer.validated_data.get("scroll_id", None)
        size = serializer.validated_data["documents_size"]
        query = serializer.validated_data.get("query")
        fields = serializer.validated_data.get("fields", None)
        return_only_docs = serializer.validated_data.get("with_meta", False)
        project = self.get_object()

        indices = project.get_available_or_all_project_indices(indices)
        if not indices:
            raise ValidationError("No indices available for scrolling.")

        ec = ElasticCore()
        documents = ec.scroll(indices=indices, query=query, scroll_id=scroll_id, size=size, with_meta=return_only_docs, fields=fields)
        return Response(documents)


    @action(detail=True, methods=['get'])
    def get_fields(self, request, pk=None, project_pk=None):
        """Returns list of fields from all Elasticsearch indices inside the project."""
        project_object = self.get_object()

        # Fetch the indices to return an empty list for project with empty
        # indices.
        project_indices = list(project_object.get_indices())
        if not project_indices:
            return Response([])

        fields = project_object.get_elastic_fields()
        field_map = {}

        for field in fields:
            if field['index'] not in field_map:
                field_map[field['index']] = []
            field_info = dict(field)
            del field_info['index']
            field_map[field['index']].append(field_info)

        field_map_list = [{'index': k, 'fields': v} for k, v in field_map.items()]
        return Response(field_map_list, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectGetSpamSerializer, permission_classes=[ExtraActionResource])
    def get_spam(self, request, pk=None):
        """
        Analyses Elasticsearch inside the project to detect frequently occuring texts.
        Returns list of potential spam messages with frequently co-occurring features.
        """
        serializer = ProjectGetSpamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        indices = list(self.get_object().get_indices())
        if not indices:
            return Response([])

        detector = SpamDetector(indices)

        all_fields = ElasticCore().get_fields(indices)
        fields = detector.filter_fields(serializer.validated_data["common_feature_fields"], all_fields)
        serializer.validated_data["common_feature_fields"] = fields  # Since we're unpacking all the data in the serializer, gonna overwrite what's inside it for comfort.

        response = detector.get_spam_content(**serializer.validated_data)
        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectGetFactsSerializer, permission_classes=[IsAuthenticated, ExtraActionResource])
    def get_facts(self, request, pk=None, project_pk=None):
        """
        Returns existing fact names and values from Elasticsearch.
        """
        serializer = ProjectGetFactsSerializer(data=request.data)

        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        indices = serializer.validated_data["indices"]
        indices = [index["name"] for index in indices]

        # retrieve and validate project indices
        project = self.get_object()
        project_indices = project.get_available_or_all_project_indices(indices)  # Gives all if n   one, the default, is entered.

        if not project_indices:
            return Response([])

        vals_per_name = serializer.validated_data['values_per_name']
        include_values = serializer.validated_data['output_type']
        fact_map = ElasticAggregator(indices=project_indices).facts(size=vals_per_name, include_values=include_values)

        if include_values:
            fact_map_list = [{'name': k, 'values': v} for k, v in fact_map.items()]
        else:
            fact_map_list = [v for v in fact_map]
        return Response(fact_map_list, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def get_indices(self, request, pk=None, project_pk=None):
        """Returns list of available indices in project."""
        project_object = self.get_object()
        project_indices = {"indices": list(project_object.get_indices())}
        return Response(project_indices)


    @action(detail=True, methods=['post'], serializer_class=ProjectSimplifiedSearchSerializer, permission_classes=[ExtraActionResource])
    def search(self, request, pk=None, project_pk=None):
        """Simplified search interface for making Elasticsearch queries."""
        serializer = ProjectSimplifiedSearchSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        project_object = self.get_object()
        project_indices = list(project_object.get_indices())
        project_fields = project_object.get_elastic_fields(path_list=True)
        # test if indices exist
        if not project_indices:
            raise ProjectValidationFailed(detail="Project has no indices")
        # test if indices are valid
        if serializer.validated_data['match_indices']:
            if not set(serializer.validated_data['match_indices']).issubset(set(project_indices)):
                raise ProjectValidationFailed(detail=f"Index names are not valid for this project. allowed values are: {project_indices}")
        # test if fields are valid
        if serializer.validated_data['match_fields']:
            if not set(serializer.validated_data['match_fields']).issubset(set(project_fields)):
                raise ProjectValidationFailed(detail=f"Fields names are not valid for this project. allowed values are: {project_fields}")

        es = ElasticSearcher(indices=project_indices, output=ElasticSearcher.OUT_DOC)
        q = Query(operator=serializer.validated_data['operator'])
        # if input is string, convert to list
        # if unknown format, return error
        match_text = serializer.validated_data['match_text']
        if isinstance(match_text, list):
            match_texts = [str(item) for item in match_text if item]
        elif isinstance(match_text, str):
            match_texts = [match_text]
        else:
            return Response({'error': f'match text is in unknown format: {match_text}'}, status=status.HTTP_400_BAD_REQUEST)
        # add query filters
        for item in match_texts:
            q.add_string_filter(item, match_type=serializer.validated_data["match_type"])
        # update query
        es.update_query(q.query)
        # retrieve results
        results = es.search(size=serializer.validated_data["size"])
        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSearchByQuerySerializer, permission_classes=[ExtraActionResource])
    def search_by_query(self, request, pk=None, project_pk=None):
        """Executes **raw** Elasticsearch query on all project indices."""
        project: Project = self.get_object()
        serializer = ProjectSearchByQuerySerializer(data=request.data)

        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        indices = project.get_available_or_all_project_indices(serializer.validated_data["indices"])

        if not indices:
            raise ProjectValidationFailed(detail="No indices supplied and project has no indices")

        es = ElasticSearcher(indices=indices, output=ElasticSearcher.OUT_DOC_WITH_TOTAL_HL_AGGS)

        es.update_query(serializer.validated_data["query"])
        results = es.search()
        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectMultiTagSerializer, permission_classes=[ExtraActionResource])
    def multitag_text(self, request, pk=None, project_pk=None):
        """
        Applies list of tagger objects inside project to any text.
        This is different from Tagger Group as **all** taggers in project are used and they do not have to reside in the same Tagger Group.
        Returns list of tags.
        """
        serializer = ProjectMultiTagSerializer(data=request.data)
        # validate serializer
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        # get project object
        project_object = self.get_object()
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
        # tag text using celery group primitive
        group_task = group(apply_tagger.s(tagger.pk, text, input_type='text', lemmatize=lemmatize, feedback=feedback) for tagger in taggers)
        group_results = [a for a in group_task.apply(queue=CELERY_SHORT_TERM_TASK_QUEUE).get() if a]

        # remove non-hits
        if hide_false is True:
            group_results = [a for a in group_results if a['result']]
        # if feedback was enabled, add urls
        group_results = [add_finite_url_to_feedback(a, request) for a in group_results]
        # sort & return tags
        sorted_tags = sorted(group_results, key=lambda k: k['probability'], reverse=True)
        return Response(sorted_tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactValuesSerializer, permission_classes=[ExtraActionResource])
    def autocomplete_fact_values(self, request, pk=None, project_pk=None):

        serializer = ProjectSuggestFactValuesSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        project_object: Project = self.get_object()
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)
        if not indices:
            return Response([])

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']
        fact_name = serializer.validated_data['fact_name']

        autocomplete = Autocomplete(project_object, indices, limit)
        fact_values = autocomplete.get_fact_values(startswith, fact_name)

        return Response(fact_values, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactNamesSerializer, permission_classes=[ExtraActionResource])
    def autocomplete_fact_names(self, request, pk=None, project_pk=None):

        serializer = ProjectSuggestFactNamesSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        project_object = self.get_object()
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project_object.get_available_or_all_project_indices(indices)

        if not indices:
            return Response([])

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']

        autocomplete = Autocomplete(project_object, indices, limit)
        fact_values = autocomplete.get_fact_names(startswith)

        return Response(fact_values, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def get_resource_counts(self, request, pk=None, project_pk=None):
        proj = self.get_object()
        response = {
            'num_lexicons': proj.lexicon_set.count(),
            'num_torchtaggers': proj.torchtagger_set.count(),
            'num_taggers': proj.tagger_set.count(),
            'num_tagger_groups': proj.taggergroup_set.count(),
            'num_embeddings': proj.embedding_set.count(),
            'num_clusterings': proj.clusteringresult_set.count(),
            'num_regex_taggers': proj.regextagger_set.count(),
            'num_regex_tagger_groups': proj.regextaggergroup_set.count(),
            'num_anonymizers': proj.anonymizer_set.count(),
            'num_mlp_workers': proj.mlpworker_set.count(),
            'num_reindexers': proj.reindexer_set.count(),
            'num_dataset_importers': proj.reindexer_set.count()
        }

        return Response(response, status=status.HTTP_200_OK)
