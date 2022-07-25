# Create your views here.
from typing import List

import elasticsearch
import texta_elastic
from elasticsearch_dsl import Q, Search
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from texta_tools.text_splitter import TextSplitter

from toolkit.core.project.models import Project
from toolkit.elastic.document_importer.serializers import InsertDocumentsSerializer, UpdateSplitDocumentSerializer
from toolkit.elastic.index.models import Index
from toolkit.helper_functions import get_core_setting
from toolkit.permissions.project_permissions import ProjectEditAccessAllowed
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import DEPLOY_KEY


def validate_index_and_project_perms(request, project_pk: int, index: str):
    project: Project = get_object_or_404(Project, pk=project_pk)
    if project.users.filter(pk=request.user.pk).exists() is False:
        raise PermissionDenied(f"User '{request.user.username}' does not have access to this project!")

    if index not in project.get_indices():
        raise PermissionDenied(f"You do not have access to this index!")


class DocumentImportView(GenericAPIView):
    serializer_class = InsertDocumentsSerializer
    permission_classes = (ProjectEditAccessAllowed, permissions.IsAuthenticated)


    @staticmethod
    def get_indices_with_timestamp(index_base: str) -> List[dict]:
        """
        Using the index_base as a base, returns all the indices in Elasticsearch
        that have it inside their names along with their timestamps to be used in
        index rotation.
        :param index_base: Limitation on which indices to pull.
        :return: List of dictionaries that contain the 'name' and 'timestamp' of all indices that have the base_name inside their name.
        """
        ec = ElasticCore()

        index_store = []
        indices = ec.get_index_settings(f"{index_base}*")
        for index_name, index_settings in indices.items():
            settings = index_settings["settings"]
            unix_timestamp: str = settings["index"]["creation_date"]
            index_store.append({"name": index_name, "creation_date": int(unix_timestamp)})
        return index_store


    @staticmethod
    def get_new_index_name(project_id: int, indices: List[str] = []):
        """
        Creates a name for the new index based on the number of documents already in the project-related indices.
        New name is given based on the number of indices matching the base name pattern.
        This prevents the indices from getting too large during production.
        """
        base_index_name = f"texta-{DEPLOY_KEY}-import-project-{project_id}"

        indices = DocumentImportView.get_indices_with_timestamp(base_index_name)
        sorted_indices = sorted(indices, reverse=True, key=lambda x: x["creation_date"])

        # if no indices exist for the pattern, use base name
        if not sorted_indices:
            return base_index_name
        # get last index name
        last_index_name = sorted_indices[0]["name"]
        # count documents in last index
        last_index_count = ElasticDocument(index=last_index_name).count()
        # compare count
        if last_index_count >= get_core_setting("TEXTA_ES_MAX_DOCS_PER_INDEX"):
            # generate new name based on number of existing indices
            new_index_name = f"{base_index_name}-{len(sorted_indices)}"
            return new_index_name
        return last_index_name


    def _normalize_missing_index_values(self, documents: List[dict], project_id: int, indices: List):
        """
        Adds an _index value to documents lacking it, indexes without it will also be rolled over.
        :param documents: Elasticsearch documents that are being changed.
        :param project_id: Project id that's used in the naming process to distinguish between duplicates.
        :param indices: List of index names already in the project, used to fetch rollover number.
        :return:
        """
        index_name = DocumentImportView.get_new_index_name(project_id, indices=indices)
        new_index = False
        for document in documents:
            document["_index"] = index_name
            new_index = True
        return documents, index_name, new_index


    def _split_documents_per_index(self, allowed_indices: List[str], documents: List[dict]):
        """
        Splits documents into three groups of allowed_permissions, failed_permissions and lacking
        any information of it at all (failed).
        :param allowed_indices: List of indices that are allowed.
        :param documents: List of Elasticsearch documents that should contain index information.
        :return: Three lists of the grouped permissions.
        """
        correct_permissions_indices = []
        failed_permissions_indices = []
        missing_indices = []

        for document in documents:
            index = document.get("_index", None)
            if index is None:
                missing_indices.append(document)
            elif index in allowed_indices:
                correct_permissions_indices.append(document)
            else:
                failed_permissions_indices.append(document)

        return correct_permissions_indices, failed_permissions_indices, missing_indices


    def _split_text(self, documents: List[dict], fields: List[str]):
        """
        Splits texts that are too large inside the list of documents.
        :param documents: Documents to split by size.
        :param fields: Which fields should be used for the splitting process.
        :return: Potentially split documents for the bulk insert generator.
        """
        if fields:
            splitter = TextSplitter()
            container = []
            for field in fields:
                for document in documents:
                    text = document["_source"].get(field, "")
                    if text:
                        pages = splitter.split(text)
                        content = document["_source"]
                        for page in pages:
                            content = {**content, **{"page": page["page"], field: page["text"]}}
                            container.append({
                                "_index": document["_index"],
                                "_source": content,
                                "_type": document.get("_type", "_doc")
                            })
                    else:
                        container.append(document)
            return container
        else:
            return documents


    def post(self, request, pk: int):
        ed = ElasticDocument(index=None)

        # Validate payload and project permissions.
        serializer: InsertDocumentsSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=pk)
        if project.users.filter(pk=request.user.pk).exists() is False:
            raise PermissionDenied("You do not have permissions for this project!")

        # Split indices on whether they have index access or lack any index details at all.
        documents = serializer.validated_data["documents"]
        split_fields = serializer.validated_data["split_text_in_fields"]
        indices = project.get_indices()

        correct_actions, failed_actions, missing_actions = self._split_documents_per_index(allowed_indices=indices, documents=documents)
        missing_actions, index_name, has_new_index = self._normalize_missing_index_values(missing_actions, project.pk, indices)
        split_actions = self._split_text(correct_actions + missing_actions, split_fields)

        if has_new_index:
            ed.core.create_index(index_name)
            ed.core.add_texta_facts_mapping(index_name)
            index, is_created = Index.objects.get_or_create(name=index_name, is_open=True, defaults={"added_by": request.user.username})
            project.indices.add(index)

        # Send the documents to Elasticsearch.
        success_count, errors = ed.bulk_add_generator(actions=split_actions, stats_only=False)
        return Response(
            {
                "successfully_indexed": success_count,
                "errors": errors,
                "failed_index_permissions": len(failed_actions)
            }
        )


class DocumentInstanceView(GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = EmptySerializer


    def get_queryset(self):
        return None


    def get(self, request, pk: int, index: str, document_id: str):
        validate_index_and_project_perms(request, pk, index)
        ed = ElasticDocument(index)
        document = ed.get(document_id)
        if not document:
            raise NotFound(f"Could not find document with ID '{document_id}' from index '{index}'!")
        return Response(document)


    def delete(self, request, pk: int, index: str, document_id: str):
        validate_index_and_project_perms(request, pk, index)

        try:
            ed = ElasticDocument(index)
            document = ed.delete(doc_id=document_id)
            return Response(document)
        except texta_elastic.exceptions.NotFoundError:
            return Response(status=status.HTTP_404_NOT_FOUND)


    def patch(self, request, pk: int, index: str, document_id: str):
        validate_index_and_project_perms(request, pk, index)

        try:
            ed = ElasticDocument(index)
            document = ed.update(index=index, doc_id=document_id, doc=request.data)
            return Response(document)
        except elasticsearch.exceptions.RequestError as e:
            if e.error == "mapper_parsing_exception":  # TODO Extend the decorator with different variants of the request error instead.
                return Response(e.info["error"]["root_cause"], status=status.HTTP_400_BAD_REQUEST)
        except texta_elastic.exceptions.NotFoundError:
            return Response(status=status.HTTP_404_NOT_FOUND)


class UpdateSplitDocument(GenericAPIView):
    serializer_class = UpdateSplitDocumentSerializer
    permission_classes = (ProjectEditAccessAllowed, permissions.IsAuthenticated)


    def _get_split_documents_by_id(self, id_field, id_value, text_field):
        documents = []
        query = Search().query(Q("term", **{f"{id_field}.keyword": id_value})).to_dict()
        es = ElasticSearcher(query=query, field_data=[id_field, text_field], output=ElasticSearcher.OUT_RAW)
        for hit in es:
            for document in hit:
                documents.append(document)
        return documents


    def _create_new_pages(self, content, sample_doc, text_field, index):
        actions = []
        splitter = TextSplitter()
        pages = splitter.split(content)
        for page in pages:
            text = page.pop("text")
            page = {**page, **sample_doc, text_field: text}
            actions.append({"_index": index, "_source": page})
        return actions


    def _get_sample_document(self, id_field: str, id_value: str, index: str):
        query = Search().query(Q("term", **{f"{id_field}.keyword": id_value})).to_dict()
        es = ElasticSearcher(query=query, output=ElasticSearcher.OUT_RAW)
        ed = ElasticDocument(index=index)
        response = es.search()["hits"]["hits"]
        document = response[0] if response else None
        return ed, document


    def patch(self, request, pk: int, index: str):
        serializer: UpdateSplitDocumentSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_field = serializer.validated_data["id_field"]
        id_value = serializer.validated_data["id_value"]
        text_field = serializer.validated_data["text_field"]
        content = serializer.validated_data["content"]

        validate_index_and_project_perms(request, pk, index)

        ed, document = self._get_sample_document(id_field, id_value, index)
        if document:
            id_value = document["_source"].get(id_field, "")
            if id_value:
                documents = self._get_split_documents_by_id(id_field, id_value, text_field)
                if not documents: return Response("Could not find any documents given the ID field!", status=status.HTTP_400_BAD_REQUEST)
                sample_doc = documents[0]["_source"]
                response = ed.bulk_delete([document["_id"] for document in documents])  # Delete existing documents to make room for new ones.
                actions = self._create_new_pages(content, sample_doc, text_field, index)
                success_count, errors = ed.bulk_add_generator(actions=actions, stats_only=False)
                return Response({"successfully_updated": success_count, "errors": errors})
            else:
                return Response(f"Could not find the id field withing the document!", status=status.HTTP_400_BAD_REQUEST)

        return Response(f"Could not find document with the id!", status=status.HTTP_400_BAD_REQUEST)
