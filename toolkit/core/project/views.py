import rest_framework.filters as drf_filters
from celery import group
from django.db.models import Count
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import (
    ProjectGetFactsSerializer,
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
from toolkit.elastic.spam_detector import SpamDetector
from toolkit.exceptions import ProjectValidationFailed, SerializerNotValid, NonExistantModelError
from toolkit.permissions.project_permissions import (ExtraActionResource, IsSuperUser, ProjectAllowed)
from toolkit.tagger.models import Tagger
from toolkit.tagger.tasks import apply_tagger
from toolkit.tools.autocomplete import Autocomplete
from toolkit.helper_functions import apply_celery_task, add_finite_url_to_feedback
from toolkit.view_constants import (
    FeedbackIndexView
)
from toolkit.helper_functions import get_core_setting


ES_URL = get_core_setting("TEXTA_ES_URL")


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


    @action(detail=True, methods=['get'])
    def get_fields(self, request, pk=None, project_pk=None):
        """Returns list of fields from all Elasticsearch indices inside the project."""
        project_object = self.get_object()
        project_indices = list(project_object.get_indices())
        if not project_indices:
            raise ProjectValidationFailed(detail="Project has no indices")
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
        detector = SpamDetector(ES_URL, indices)

        all_fields = ElasticCore().get_fields(indices)
        fields = detector.filter_fields(serializer.validated_data["common_feature_fields"], all_fields)
        serializer.validated_data["common_feature_fields"] = fields  # Since we're unpacking all the data in the serializer, gonna overwrite what's inside it for comfort.

        response = detector.get_spam_content(**serializer.validated_data)
        return Response(response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'], serializer_class=ProjectGetFactsSerializer)
    def get_facts(self, request, pk=None, project_pk=None):
        """
        Returns existing fact names and values from Elasticsearch.
        """
        serializer = ProjectGetFactsSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        # retrieve and validate project indices
        project_indices = list(self.get_object().get_indices())
        if not project_indices:
            raise ProjectValidationFailed(detail="Project has no indices")

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
        serializer = ProjectSearchByQuerySerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        if serializer.validated_data["indices"]:
            indices = serializer.validated_data["indices"]
        else:
            indices = self.get_object().get_indices()

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
            return Response({'error': 'none of provided taggers are present. are the models ready?'}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve params
        lemmatize = serializer.validated_data['lemmatize']
        feedback = serializer.validated_data['feedback_enabled']
        text = serializer.validated_data['text']
        hide_false = serializer.validated_data['hide_false']
        # tag text using celery group primitive
        group_task = group(apply_tagger.s(tagger.pk, text, input_type='text', lemmatize=lemmatize, feedback=feedback) for tagger in taggers)
        group_results = [a for a in apply_celery_task(group_task).get() if a]
        # remove non-hits
        if hide_false == True:
            group_results = [a for a in group_results if a['result']]
        # if feedback was enabled, add urls
        group_results = [add_finite_url_to_feedback(a, request) for a in group_results]
        # sort & return tags
        sorted_tags = sorted(group_results, key=lambda k: k['probability'], reverse=True)
        return Response(sorted_tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactValuesSerializer, permission_classes=[ExtraActionResource])
    def autocomplete_fact_values(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectSuggestFactValuesSerializer(data=data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        project_object = self.get_object()
        project_indices = list(project_object.get_indices())
        if not project_indices:
            raise ProjectValidationFailed(detail="Project has no indices")

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']
        fact_name = serializer.validated_data['fact_name']

        autocomplete = Autocomplete(project_object, project_indices, limit)
        fact_values = autocomplete.get_fact_values(startswith, fact_name)

        return Response(fact_values, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactNamesSerializer, permission_classes=[ExtraActionResource])
    def autocomplete_fact_names(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectSuggestFactNamesSerializer(data=data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)
        project_object = self.get_object()
        project_indices = list(project_object.get_indices())
        if not project_indices:
            raise ProjectValidationFailed(detail="Project has no indices")

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']

        autocomplete = Autocomplete(project_object, project_indices, limit)
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
            'num_embeddings': proj.embedding_set.count()
        }

        return Response(response, status=status.HTTP_200_OK)
