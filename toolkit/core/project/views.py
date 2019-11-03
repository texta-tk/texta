from django.db.models.query import QuerySet
from rest_framework import viewsets, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from toolkit.permissions.project_permissions import ProjectAllowed
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import (
    ProjectSerializer,
    ProjectGetFactsSerializer,
    ProjectSimplifiedSearchSerializer,
    ProjectSearchByQuerySerializer,
    ProjectMultiTagSerializer,
    ProjectSuggestFactValuesSerializer,
    ProjectSuggestFactNamesSerializer,
)
from toolkit.serializer_constants import ProjectResourceImportModelSerializer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query
from toolkit.tagger.models import Tagger
from toolkit.core.task.models import Task
from toolkit.tagger.tasks import apply_tagger
from toolkit.view_constants import ImportModel
from toolkit.tools.autocomplete import Autocomplete

from celery import group

class ProjectViewSet(viewsets.ModelViewSet, ImportModel):
    # Disable default pagination
    pagination_class = None
    serializer_class = ProjectSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectAllowed,
    )

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def get_queryset(self):
        queryset = Project.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = (queryset.filter(owner=current_user) | queryset.filter(users=current_user)).distinct()
        return queryset


    @action(detail=True, methods=['get'])
    def get_fields(self, request, pk=None, project_pk=None):
        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)
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


    @action(detail=True, methods=['get', 'post'], serializer_class=ProjectGetFactsSerializer)
    def get_facts(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectGetFactsSerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)

        vals_per_name = serializer.validated_data['values_per_name']
        include_values = serializer.validated_data['output_type']
        fact_map = ElasticAggregator(indices=project_indices).facts(size=vals_per_name, include_values=include_values)

        if include_values:
            fact_map_list = [{'name': k, 'values': v} for k, v in fact_map.items()]
        else:
            fact_map_list = [v for v in fact_map]

        return Response(fact_map_list, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSimplifiedSearchSerializer)
    def search(self, request, pk=None, project_pk=None):
        data = request.POST
        serializer = ProjectSimplifiedSearchSerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        project_object = self.get_object()
        project_indices = list(project_object.indices)
        project_fields = project_object.get_elastic_fields(path_list=True)
        # test if indices exist
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)
        # test if indices are valid
        if serializer.validated_data['match_indices']:
            if not set(serializer.validated_data['match_indices']).issubset(set(project_indices)):
                return Response({'error': f'index names are not valid for this project. allowed values are: {project_indices}'},
                                status=status.HTTP_400_BAD_REQUEST)
        # test if fields are valid
        if serializer.validated_data['match_fields']:
            if not set(serializer.validated_data['match_fields']).issubset(set(project_fields)):
                return Response({'error': f'fields names are not valid for this project. allowed values are: {project_fields}'},
                                status=status.HTTP_400_BAD_REQUEST)
                                
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


    @action(detail=True, methods=['post'], serializer_class=ProjectSearchByQuerySerializer)
    def search_by_query(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectSearchByQuerySerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        project_object = self.get_object()
        project_indices = list(project_object.indices)

        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST) 

        es = ElasticSearcher(indices=project_indices, output=ElasticSearcher.OUT_DOC_HL)
        es.update_query(serializer.validated_data['query'])
        results = es.search()

        return Response(results, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectMultiTagSerializer)
    def multitag_text(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectMultiTagSerializer(data=data)
        # validate serializer
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        # get project object
        project_object = self.get_object()
        # get available taggers from project
        taggers = Tagger.objects.filter(project=project_object).filter(task__status=Task.STATUS_COMPLETED)
        # filter again
        taggers = taggers.filter(pk__in=serializer.validated_data['taggers'])
        # error if filtering resulted 0 taggers
        if not taggers:
            return Response({'error': 'none of provided taggers are present. are the models ready?'}, status=status.HTTP_400_BAD_REQUEST)
        # tag text using celery group primitive
        text = serializer.validated_data['text']
        tags = group(apply_tagger.s(text, tagger.pk, 'text') for tagger in taggers).apply()
        tags = [tag for tag in tags.get() if tag]
        # sort & return tags
        sorted_tags = sorted(tags, key=lambda k: k['probability'], reverse=True)
        return Response(sorted_tags, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactValuesSerializer)
    def autocomplete_fact_values(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectSuggestFactValuesSerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']
        fact_name = serializer.validated_data['fact_name']

        autocomplete = Autocomplete(project_object, project_indices, limit)
        fact_values = autocomplete.get_fact_values(startswith, fact_name)


        return Response(fact_values, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactNamesSerializer)
    def autocomplete_fact_names(self, request, pk=None, project_pk=None):
        data = request.data
        serializer = ProjectSuggestFactNamesSerializer(data=data)
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        project_object = self.get_object()
        project_indices = list(project_object.indices)
        if not project_indices:
            return Response({'error': 'project has no indices'}, status=status.HTTP_400_BAD_REQUEST)

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']

        autocomplete = Autocomplete(project_object, project_indices, limit)
        fact_values = autocomplete.get_fact_names(startswith)


        return Response(fact_values, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get'])
    def get_resource_counts(self, request, pk=None, project_pk=None):
        proj = self.get_object()
        response = {
            'num_neurotaggers': proj.neurotagger_set.count(),
            'num_taggers': proj.tagger_set.count(),
            'num_tagger_groups': proj.taggergroup_set.count(),
            'num_embeddings': proj.embedding_set.count(),
            'num_embedding_clusters': proj.embeddingcluster_set.count(),
        }

        return Response(response, status=status.HTTP_200_OK)
