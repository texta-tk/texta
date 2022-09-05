import json
import pathlib
from wsgiref.util import FileWrapper

import elasticsearch
import elasticsearch_dsl
import rest_framework.filters as drf_filters
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.urls import reverse
from django.utils._os import safe_join
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.query import Query
from texta_elastic.searcher import ElasticSearcher
from texta_elastic.spam_detector import SpamDetector

from toolkit.core.project.models import Project
from toolkit.core.project.serializers import (CountIndicesSerializer, ExportSearcherResultsSerializer, HandleIndicesSerializer, HandleProjectAdministratorsSerializer, HandleUsersSerializer, ProjectDocumentSerializer, ProjectFactAggregatorSerializer, ProjectGetFactsSerializer,
                                              ProjectGetSpamSerializer, ProjectSearchByQuerySerializer, ProjectSerializer, ProjectSimplifiedSearchSerializer, ProjectSuggestFactNamesSerializer, ProjectSuggestFactValuesSerializer)
from toolkit.elastic.decorators import elastic_view
from toolkit.elastic.index.models import Index
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.tools.serializers import ElasticScrollSerializer
from toolkit.exceptions import InvalidInputDocument, ProjectValidationFailed, SerializerNotValid
from toolkit.helper_functions import hash_string
from toolkit.permissions.project_permissions import (
    AuthorProjAdminSuperadminAllowed,
    ExtraActionAccessInApplications,
    OnlySuperadminAllowed,
    ProjectAccessInApplicationsAllowed,
    ProjectEditAccessAllowed
)
from toolkit.settings import RELATIVE_PROJECT_DATA_PATH, SEARCHER_FOLDER_KEY
from toolkit.tools.autocomplete import Autocomplete
from toolkit.view_constants import FeedbackIndexView


class ProtectedServeApi(APIView):
    permission_classes = (IsAuthenticated,)


    def get(self, request, path, document_root=None, show_indexes=False):
        path = safe_join(document_root, path)
        path_exists = pathlib.Path(path).exists()
        if path_exists is False:
            raise PermissionDenied("File does not exist!")

        return StreamingHttpResponse(FileWrapper(open(path, "rb")))


class ProtectedFileServe(APIView):
    permission_classes = (IsAuthenticated,)


    def get(self, request, project_id: int, application: str, file_name: str, document_root=None):
        path = safe_join(RELATIVE_PROJECT_DATA_PATH, str(project_id), application, file_name)

        # Safety checks.
        is_authorized = Project.objects.filter(pk=project_id, users__in=[request.user]).exists()
        path_exists = pathlib.Path(path).exists()
        if is_authorized is False:
            raise PermissionDenied("Given user is not added in the project!")
        if path_exists is False:
            raise PermissionDenied("File does not exist!")

        # Return nicely if it passes all the checks.
        return StreamingHttpResponse(FileWrapper(open(path, "rb")))


class ExportSearchView(APIView):
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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

            fields = serializer.validated_data["fields"]

            original_query = elasticsearch_dsl.Search().from_dict(query).source(fields)
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
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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
        include_values = serializer.validated_data['include_values']
        fact_name = serializer.validated_data['fact_name']
        include_doc_path = serializer.validated_data['include_doc_path']
        exclude_zero_spans = serializer.validated_data['exclude_zero_spans']
        mlp_doc_path = serializer.validated_data['mlp_doc_path']

        aggregator = ElasticAggregator(indices=project_indices)

        if mlp_doc_path and exclude_zero_spans:
            # If exclude_zerp_spans is enabled and mlp_doc_path specified, the other values don't have any effect -
            # this behaviour might need to change at some point
            fact_map = aggregator.facts(size=1, include_values=True, include_doc_path=True, exclude_zero_spans=exclude_zero_spans)

        else:
            fact_map = aggregator.facts(size=vals_per_name, include_values=include_values, filter_by_fact_name=fact_name, include_doc_path=include_doc_path, exclude_zero_spans=exclude_zero_spans)

        if fact_name:
            fact_map_list = [v for v in fact_map]

        elif mlp_doc_path and exclude_zero_spans:
            # Return only fact names where doc_path contains mlp_doc_path as a parent field and facts have spans.
            # NB! Doesn't take into account the situation where facts have the same name, but different doc paths! Could happen!
            fact_map_list = [k for k, v in fact_map.items() if v and mlp_doc_path == v[0]["doc_path"].rsplit(".", 1)[0]]

        elif include_values:
            fact_map_list = [{'name': k, 'values': v} for k, v in fact_map.items()]
        else:
            fact_map_list = [v for v in fact_map]
        return Response(fact_map_list, status=status.HTTP_200_OK)


class AggregateFactsView(APIView):
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
    def post(self, request, project_pk: int):
        """
        Returns existing fact names and values from Elasticsearch.
        """
        serializer = ProjectFactAggregatorSerializer(data=request.data)

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

        key_field = serializer.validated_data["key_field"]
        value_field = serializer.validated_data["value_field"]
        filter_by_key = serializer.validated_data["filter_by_key"]
        max_count = serializer.validated_data["max_count"]
        query = serializer.validated_data["query"]

        if isinstance(query, str):
            query = json.loads(query)

        aggregator = ElasticAggregator(indices=project_indices, query=query)
        results = aggregator.facts_abstract(key_field=key_field, value_field=value_field, filter_by_key=filter_by_key, size=max_count)

        return Response(results, status=status.HTTP_200_OK)


class GetIndicesView(APIView):
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
    def get(self, request, project_pk: int):
        """Returns list of available indices in project."""
        project_object = get_object_or_404(Project, pk=project_pk)
        self.check_object_permissions(request, project_object)
        project_indices = {"indices": list(project_object.get_indices())}
        return Response(project_indices)


class SearchView(APIView):
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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
    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]


    @elastic_view
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
    """Get document by ID from specified indices."""

    permission_classes = [IsAuthenticated, ProjectAccessInApplicationsAllowed]
    serializer_class = ProjectDocumentSerializer


    @elastic_view
    def post(self, request, project_pk: int):
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
        ProjectEditAccessAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = ProjectFilter
    ordering_fields = ('id', 'title', 'users_count', 'indices_count',)


    def get_queryset(self):
        current_user = self.request.user

        if not current_user.is_superuser:
            user_scopes = json.loads(current_user.profile.scopes)
            user_scopes_str = " ".join(user_scopes)

            in_user = Project.objects.filter(users=current_user)
            in_admin = Project.objects.filter(administrators=current_user)

            # TODO Revisit this part.
            if user_scopes:
                scopes_filter = Project.objects.filter(scopes__contains=user_scopes[0])
                for scope in user_scopes[1:]:
                    scopes_filter = scopes_filter | Project.objects.filter(scopes__contains=scope)

                query_filter = (in_user | in_admin | scopes_filter)

            else:
                query_filter = (in_user | in_admin)

            return query_filter.distinct().order_by('-id').prefetch_related("users", "administrators", "indices")
        else:
            return Project.objects.all().order_by('-id').prefetch_related("users", "administrators", "indices")


    @action(detail=True, methods=['post'], serializer_class=HandleIndicesSerializer, permission_classes=[OnlySuperadminAllowed])
    def add_indices(self, request, pk=None, project_pk=None):
        project: Project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        indices = [index.name for index in serializer.validated_data["indices"]]
        ec = ElasticCore()
        exists = ec.check_if_indices_exist(indices)
        if exists and indices:
            for index_name in indices:
                index, is_created = Index.objects.get_or_create(name=index_name)
                project.indices.add(index)
            return Response({"detail": f"Added indices '{str(indices)}' to the project!"})
        else:
            raise ValidationError(f"Could not validate indices f'{str(indices)}'")


    @action(detail=True, methods=['post'], serializer_class=HandleIndicesSerializer, permission_classes=[AuthorProjAdminSuperadminAllowed])
    def remove_indices(self, request, pk=None, project_pk=None):
        project: Project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        indices_names = [index.name for index in serializer.validated_data["indices"]]
        ec = ElasticCore()
        indices = project.indices.filter(name__in=indices_names)
        project.indices.remove(*indices)
        return Response({"detail": f"Removed indices '{str(indices_names)}' from the project!"})


    @action(detail=True, methods=['post'], serializer_class=HandleUsersSerializer, permission_classes=[AuthorProjAdminSuperadminAllowed])
    def add_users(self, request, pk=None, project_pk=None):
        project: Project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = [str(user) for user in serializer.validated_data["users"]]
        user_filter = Q(username__in=users)
        users = User.objects.filter(user_filter)
        project.users.add(*users)
        return Response({"detail": f"Added users '{str([user for user in users])}' into the project!"})


    @action(detail=True, methods=['post'], serializer_class=HandleUsersSerializer, permission_classes=[AuthorProjAdminSuperadminAllowed])
    def remove_users(self, request, pk=None, project_pk=None):
        project: Project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = [str(user) for user in serializer.validated_data["users"]]
        user_filter = Q(username__in=users)
        users = User.objects.filter(user_filter)
        project.users.remove(*users)
        return Response({"detail": f"Removed users '{str([user for user in users])}' from the project!"})


    @action(detail=True, methods=['post'], serializer_class=HandleProjectAdministratorsSerializer, permission_classes=[AuthorProjAdminSuperadminAllowed])
    def add_project_admins(self, request, pk=None, project_pk=None):
        project: Project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = [str(user) for user in serializer.validated_data["project_admins"]]
        user_filter = Q(username__in=users)
        users = User.objects.filter(user_filter)
        project.administrators.add(*users)
        return Response({"detail": f"Added project administrators '{str([user for user in users])}' into the project!"})


    @action(detail=True, methods=['post'], serializer_class=HandleProjectAdministratorsSerializer, permission_classes=[AuthorProjAdminSuperadminAllowed])
    def remove_project_admins(self, request, pk=None, project_pk=None):
        project: Project = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        users = [str(user) for user in serializer.validated_data["project_admins"]]
        user_filter = Q(username__in=users)
        users = User.objects.filter(user_filter)
        project.administrators.remove(*users)
        return Response({"detail": f"Removed project administrators '{str([user for user in users])}' from the project!"})


    @action(detail=True, methods=['post'], serializer_class=CountIndicesSerializer, permission_classes=[ExtraActionAccessInApplications])
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


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactValuesSerializer, permission_classes=[ExtraActionAccessInApplications])
    def autocomplete_fact_values(self, request, pk=None, project_pk=None):
        serializer = ProjectSuggestFactValuesSerializer(data=request.data)
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        project_object: Project = self.get_object()
        indices = serializer.validated_data["indices"]
        indices = project_object.get_available_or_all_project_indices(indices)
        if not indices:
            return Response([])

        limit = serializer.validated_data['limit']
        startswith = serializer.validated_data['startswith']
        fact_name = serializer.validated_data['fact_name']

        autocomplete = Autocomplete(project_object, indices, limit)
        fact_values = autocomplete.get_fact_values(startswith, fact_name)

        return Response(fact_values, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=ProjectSuggestFactNamesSerializer, permission_classes=[ExtraActionAccessInApplications])
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
        response = proj.get_resource_counts()
        return Response(response, status=status.HTTP_200_OK)
