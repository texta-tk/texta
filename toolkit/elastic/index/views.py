import logging
from typing import List, Optional

import rest_framework.filters as drf_filters
from django.db import transaction
from django.http import JsonResponse
from django_filters import rest_framework as filters
from rest_framework import mixins, status, views, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from texta_elastic.core import ElasticCore

from toolkit.elastic.decorators import elastic_connection
from toolkit.elastic.exceptions import ElasticIndexAlreadyExists
from toolkit.elastic.index.models import Index
from toolkit.elastic.index.serializers import (
    IndexBulkDeleteSerializer, IndexSerializer, IndexUpdateSerializer
)
from toolkit.helper_functions import chunks
from toolkit.permissions.project_permissions import IsSuperUser
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import ERROR_LOGGER, TEXTA_TAGS_KEY


class IndicesFilter(filters.FilterSet):
    id = filters.CharFilter('id', lookup_expr='exact')
    name = filters.CharFilter('name', lookup_expr='icontains')
    is_open = filters.BooleanFilter("is_open")

    class Meta:
        model = Index
        fields = []


class ElasticGetIndices(views.APIView):
    permission_classes = (IsSuperUser,)

    def get(self, request):
        """
        Returns **all** available indices from Elasticsearch.
        This is different from get_indices action in project view as it lists **all** indices in Elasticsearch.
        """
        indices = [{"id": index.id, "name": index.name} for index in Index.objects.all()]
        return JsonResponse(indices, safe=False, status=status.HTTP_200_OK)


class IndexViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    queryset = Index.objects.all()
    serializer_class = IndexSerializer
    permission_classes = [IsSuperUser]

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    pagination_class = None
    filterset_class = IndicesFilter

    ordering_fields = (
        'id',
        'name',
        'is_open'
    )

    def _resolve_cluster_differences(self, mapping_dict: dict) -> Optional[dict]:
        # Trying to support ES6 and ES7 mapping structure.
        has_properties = True if "properties" in mapping_dict else False
        if has_properties:
            return mapping_dict
        # In this case, the mapping is a a plain dictionary because no fields exist.
        else:
            for key in mapping_dict.keys():
                if "properties" in mapping_dict[key]:
                    return mapping_dict[key]

    def _check_for_facts(self, index_mappings: dict, index_name: str):
        mapping_dict = index_mappings.get(index_name, {}).get("mappings", None)
        # In case we have a faulty sync.
        if mapping_dict is None:
            return False

        mapping_dict = self._resolve_cluster_differences(mapping_dict)

        # In case there are no fields inside the mapping because it's a freshly
        # created index.
        if mapping_dict:
            properties = mapping_dict["properties"]
            facts = properties.get(TEXTA_TAGS_KEY, {})
            typing = facts.get("type", None)
            if typing == "nested":
                return True
            else:
                return False
        else:
            return False

    def list(self, request, *args, **kwargs):
        ec = ElasticCore()

        response = super(IndexViewSet, self).list(request, *args, **kwargs)

        data = response.data  # Get the paginated and sorted queryset results.
        open_indices = [index for index in data if index["is_open"]]
        mappings = ec.es.indices.get_mapping()

        # Doing a stats request with no indices causes trouble.
        if open_indices:
            stats = ec.get_index_stats()

            # Update the paginated and sorted queryset results.
            for index in response.data:
                name = index["name"]
                is_open = index["is_open"]
                if is_open:
                    has_texta_facts_mapping = self._check_for_facts(index_mappings=mappings, index_name=name)
                    if name in stats:
                        index.update(**stats[name], has_validated_facts=has_texta_facts_mapping)
                    else:
                        index.update(has_validated_facts=False)
                else:
                    # For the sake of courtesy on the front-end, make closed indices values zero.
                    index.update(size=0, doc_count=0, has_validated_facts=False)

        return response

    def retrieve(self, request, *args, **kwargs):
        ec = ElasticCore()
        response = super(IndexViewSet, self).retrieve(*args, *kwargs)
        if response.data["is_open"]:
            index_name = response.data["name"]
            mapping = ec.es.indices.get_mapping(index_name)
            has_validated_facts = self._check_for_facts(mapping, index_name)
            stats = ec.get_index_stats()
            response.data.update(**stats[index_name], has_validated_facts=has_validated_facts)
        else:
            response.data.update(size=0, doc_count=0, has_validated_facts=False)

        return response

    def create(self, request, **kwargs):
        data = IndexSerializer(data=request.data)
        data.is_valid(raise_exception=True)

        es = ElasticCore()
        index = data.validated_data["name"]
        is_open = data.validated_data["is_open"]
        description = data.validated_data["description"]
        added_by = data.validated_data["added_by"]
        test = data.validated_data["test"]
        source = data.validated_data["source"]
        client = data.validated_data["client"]
        domain = data.validated_data["domain"]

        # Using get_or_create to avoid unique name constraints on creation.
        if es.check_if_indices_exist([index]):
            # Even if the index already exists, create the index object just in case
            index, is_created = Index.objects.get_or_create(name=index, defaults={"added_by": request.user.username})

            if is_created:
                utc_time = es.get_index_creation_date(index)
                index.is_open = is_open
                index.description = description
                index.added_by = added_by
                index.test = test
                index.source = source
                index.client = client
                index.domain = domain
                index.created_at = utc_time
            index.save()
            raise ElasticIndexAlreadyExists()

        else:
            es.create_index(index=index)
            if not is_open:
                es.close_index(index)

            index, is_created = Index.objects.get_or_create(name=index, defaults={"added_by": request.user.username})
            if is_created:
                utc_time = es.get_index_creation_date(index)
                index.is_open = is_open
                index.description = description
                index.added_by = added_by
                index.test = test
                index.source = source
                index.client = client
                index.domain = domain
                index.created_at = utc_time
            index.save()

            return Response({"message": f"Added index {index} into Elasticsearch!"}, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None, **kwargs):
        data = IndexUpdateSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)

        index = Index.objects.get(pk=pk)

        val_list = [
            'description',
            'added_by',
            'test',
            'source',
            'client',
            'domain'
        ]

        for v_name in val_list:
            if v_name in data.validated_data:
                setattr(index, v_name, data.validated_data[v_name])

        index.save()
        return Response({"message": f"Updated index {index} into Elasticsearch!"}, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None, **kwargs):
        with transaction.atomic():
            index_name = Index.objects.get(pk=pk).name
            es = ElasticCore()
            response = es.delete_index(index_name)

            Index.objects.filter(pk=pk).delete()
            return Response({"message": f"Deleted index {index_name} from Elasticsearch!"})

    def _handle_bulk_deletion(self, index_names: List[str]):
        if index_names:
            ec = ElasticCore()
            failed_indices = []

            # Have to chunk the index names as there's a limit on how big of a request Elasticsearch will accept by size.
            index_chunks = chunks(index_names, 5)
            for indices in index_chunks:
                response = ec.delete_index(",".join(indices))
                is_acknowledged = response.get('acknowledged', False)
                if is_acknowledged is False:
                    logging.getLogger(ERROR_LOGGER).error(response)
                    failed_indices = set(list(failed_indices + indices))

            for index in failed_indices:
                ec.delete_index(index)

    @action(detail=False, methods=['post'], serializer_class=EmptySerializer)
    @elastic_connection
    def clear_read_only_blocks(self, request, project_pk=None):
        """
        Helper function for disabling read_only blocks from indices that are created
        after the cluster reaches its disk-space flood warning threshold. Sets the value of
        index.blocks.read_only_allow_delete in all indices (through a wildcard) to false.

        WARNING! These flood thresholds and blocks are set by Elasticsearch for a good reason,
        do not run this unless you have solved the problem and hand and want to unlock the indices.
        """
        ec = ElasticCore()
        ec.es.indices.put_settings(index="*", body={
            "index": {
                "blocks": {
                    "read_only_allow_delete": "false"
                }
            }
        })
        return Response({"message": "Set index.blocks.read_only_allow_delete to false!"})

    @action(detail=False, methods=['post'], serializer_class=IndexBulkDeleteSerializer)
    def bulk_delete(self, request, project_pk=None):
        serializer: IndexBulkDeleteSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Get the index names.
        ids = serializer.validated_data["ids"]
        objects = Index.objects.filter(pk__in=ids)
        index_names = [item.name for item in objects]

        self._handle_bulk_deletion(index_names)

        deleted = objects.delete()
        info = {"num_deleted": deleted[0], "deleted_types": deleted[1]}
        return Response(info, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], serializer_class=EmptySerializer)
    def sync_indices(self, request, pk=None, project_pk=None):
        ElasticCore().syncher()
        return Response({"message": "Synched everything successfully!"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['patch'], serializer_class=EmptySerializer)
    def close_index(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        es_core.close_index(index.name)
        index.is_open = False
        index.save()
        return Response({"message": f"Closed the index {index.name}"})

    @action(detail=True, methods=['patch'], serializer_class=EmptySerializer)
    def open_index(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        es_core.open_index(index.name)
        if not index.is_open:
            index.is_open = True
            index.save()

        return Response({"message": f"Opened the index {index.name}"})

    @action(detail=True, methods=['post'], serializer_class=EmptySerializer)
    def add_facts_mapping(self, request, pk=None, project_pk=None):
        es_core = ElasticCore()
        index = Index.objects.get(pk=pk)
        if index.is_open:
            es_core.add_texta_facts_mapping(index.name)
            return Response({"message": f"Added the Texta Facts mapping for: {index.name}"})
        else:
            return Response({"message": f"Index {index.name} is closed, could not add the mapping!"}, status=status.HTTP_400_BAD_REQUEST)
