import json
import pathlib

import elasticsearch
import elasticsearch_dsl
import rest_framework.filters as drf_filters
from django.db.models import Count
from django.urls import reverse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import (CountIndicesSerializer, ExportSearcherResultsSerializer, ProjectDocumentSerializer, ProjectGetFactsSerializer, ProjectGetSpamSerializer, ProjectSearchByQuerySerializer, ProjectSerializer, ProjectSimplifiedSearchSerializer,
                                              ProjectSuggestFactNamesSerializer,
                                              ProjectSuggestFactValuesSerializer)
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.query import Query
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.serializers import ElasticScrollSerializer, IndexSerializer
from toolkit.elastic.spam_detector import SpamDetector
from toolkit.exceptions import InvalidInputDocument, ProjectValidationFailed, SerializerNotValid
from toolkit.helper_functions import hash_string
from toolkit.permissions.project_permissions import (ExtraActionResource, IsSuperUser, ProjectAllowed, ProjectResourceAllowed)
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH, SEARCHER_FOLDER_KEY
from toolkit.tools.autocomplete import Autocomplete
from toolkit.view_constants import FeedbackIndexView


class ExportSearchView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        try:
            serializer = ExportSearcherResultsSerializer(data=request.data)
            model = get_object_or_404(Project, pk=project_pk)
            self.check_object_permissions(request, model)

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

            path = pathlib.Path(RELATIVE_PROJECT_DATA_PATH) / str(project_pk) / SEARCHER_FOLDER_KEY
            path.mkdir(parents=True, exist_ok=True)
            file_name = f"{hash_string(query_str)}.jl"

            with open(path / file_name, "w+", encoding="utf8") as fp:
                for item in limit_by_n_docs.scan():
                    item = item.to_dict()
                    json_string = json.dumps(item, ensure_ascii=False)
                    fp.write(f"{json_string}\n")

            url = reverse("protected_serve", kwargs={"project_id": int(project_pk), "application": SEARCHER_FOLDER_KEY, "file_name": file_name})
            return Response(request.build_absolute_uri(url))

        except elasticsearch.exceptions.RequestError:
            return Response({"detail": "Could not parse the query you sent!"}, status=status.HTTP_400_BAD_REQUEST)


class ScrollView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        serializer = ElasticScrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        indices = serializer.validated_data["indices"]
        scroll_id = serializer.validated_data.get("scroll_id", None)
        size = serializer.validated_data["documents_size"]
        query = serializer.validated_data.get("query")
        fields = serializer.validated_data.get("fields", None)
        return_only_docs = serializer.validated_data.get("with_meta", False)
        project = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project)

        indices = project.get_available_or_all_project_indices(indices)
        if not indices:
            raise ValidationError("No indices available for scrolling.")

        ec = ElasticCore()
        documents = ec.scroll(indices=indices, query=query, scroll_id=scroll_id, size=size, with_meta=return_only_docs, fields=fields)
        return Response(documents)


class GetSpamView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        """
        Analyses Elasticsearch inside the project to detect frequently occuring texts.
        Returns list of potential spam messages with frequently co-occurring features.
        """
        serializer = ProjectGetSpamSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project)
        indices = list(project.get_indices())
        if not indices:
            return Response([])

        detector = SpamDetector(indices)

        all_fields = ElasticCore().get_fields(indices)
        fields = detector.filter_fields(serializer.validated_data["common_feature_fields"], all_fields)
        serializer.validated_data["common_feature_fields"] = fields  # Since we're unpacking all the data in the serializer, gonna overwrite what's inside it for comfort.

        response = detector.get_spam_content(**serializer.validated_data)
        return Response(response, status=status.HTTP_200_OK)


class GetFieldsView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def get(self, request, project_pk: int):
        """Returns list of fields from all Elasticsearch indices inside the project."""
        project_object = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project_object)

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


class GetFactsView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        """
        Returns existing fact names and values from Elasticsearch.
        """
        serializer = ProjectGetFactsSerializer(data=request.data)

        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        indices = serializer.validated_data["indices"]
        indices = [index["name"] for index in indices]

        # retrieve and validate project indices
        project = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project)
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


class GetIndicesView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def get(self, request, project_pk: int):
        """Returns list of available indices in project."""
        project_object = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project_object)
        project_indices = {"indices": list(project_object.get_indices())}
        return Response(project_indices)


class SearchView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        """Simplified search interface for making Elasticsearch queries."""
        serializer = ProjectSimplifiedSearchSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        project_object = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project_object)
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


class SearchByQueryView(APIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        """Executes **raw** Elasticsearch query on all project indices."""
        project = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project)
        serializer = ProjectSearchByQuerySerializer(data=request.data)

        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        indices = project.get_available_or_all_project_indices(serializer.validated_data["indices"])

        if not indices:
            raise ProjectValidationFailed(detail="No indices supplied and project has no indices")

        es = None
        if serializer.validated_data["output_type"]:
            es = ElasticSearcher(indices=indices, output=serializer.validated_data["output_type"])
        else:
            es = ElasticSearcher(indices=indices, output=ElasticSearcher.OUT_DOC_WITH_TOTAL_HL_AGGS)

        es.update_query(serializer.validated_data["query"])
        results = es.search()
        return Response(results, status=status.HTTP_200_OK)


class DocumentView(GenericAPIView):
    permission_classes = [IsAuthenticated, ProjectResourceAllowed]


    def post(self, request, project_pk: int):
        """Get document by ID from specified indices."""
        project: Project = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project)

        serializer = ProjectDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        indices = project.get_available_or_all_project_indices(serializer.validated_data["indices"])
        if not indices:
            raise ProjectValidationFailed(detail="No indices supplied and project has no indices")

        doc_id = serializer.validated_data["doc_id"]
        if not doc_id:
            raise InvalidInputDocument(detail="No doc_id supplied")

        es = ElasticDocument(index=indices)
        results = es.get(doc_id)
        return Response(results, status=status.HTTP_200_OK)


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


    @action(detail=True, methods=['post'], serializer_class=CountIndicesSerializer, permission_classes=[ExtraActionResource])
    def count_indices(self, request, pk=None, project_pk=None):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid()

        indices = [{"name": name} for name in serializer.validated_data.get("indices", [])]
        serializer = IndexSerializer(data=indices, many=True)
        serializer.is_valid(raise_exception=True)

        project: Project = self.get_object()
        ed = ElasticDocument(None)

        indices = [index["name"] for index in indices]
        if indices:
            # We check for indices before to prevent the default behaviour of picking all the indices in project.
            indices = project.get_available_or_all_project_indices(indices)
            count = ed.count(indices=indices)
            return Response(count)
        else:
            return Response(0)


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

        project_object: Project = self.get_object()
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
        proj: Project = self.get_object()
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
            'num_dataset_importers': proj.datasetimport_set.count(),
            'num_bert_taggers': proj.berttagger_set.count(),
            "num_index_splitters": proj.indexsplitter_set.count()
        }

        return Response(response, status=status.HTTP_200_OK)
