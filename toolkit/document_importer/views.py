# Create your views here.
from typing import List

import elasticsearch
from elasticsearch_dsl import Q, Search
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from texta_tools.text_splitter import TextSplitter

from toolkit.core.project.models import Project
from toolkit.document_importer.serializers import InsertDocumentsSerializer, UpdateSplitDocumentSerializer
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.models import Index
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.permissions.project_permissions import ProjectAllowed
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import DEPLOY_KEY


class UpdateSplitDocument(GenericAPIView):
    serializer_class = UpdateSplitDocumentSerializer
    permission_classes = (ProjectAllowed, permissions.IsAuthenticated)


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
            actions.append({"_index": index, "_type": index, "_source": page})
        return actions


    def patch(self, request, pk: int, index: str):
        serializer: UpdateSplitDocumentSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        project: Project = get_object_or_404(Project, pk=pk)
        if request.user not in project.users.all():
            raise PermissionDenied(f"User '{request.user.username}' does not have access to this project!")

        if index not in project.get_indices():
            raise PermissionDenied(f"You do not have access to this index!")

        id_field = serializer.validated_data["id_field"]
        id_value = serializer.validated_data["id_value"]
        text_field = serializer.validated_data["text_field"]
        content = serializer.validated_data["content"]

        query = Search().query(Q("term", **{f"{id_field}.keyword": id_value})).to_dict()
        es = ElasticSearcher(query=query, output=ElasticSearcher.OUT_RAW)
        ed = ElasticDocument(index=index)
        response = es.search()["hits"]["hits"]
        document = response[0] if response else None
        if document:
            id_value = document["_source"].get(id_field, "")
            if id_value:
                documents = self._get_split_documents_by_id(id_field, id_value, text_field)
                if not documents: return Response("Could not find any documents given the ID field!", status=status.HTTP_400_BAD_REQUEST)
                sample_doc = documents[0]["_source"]
                response = ed.bulk_delete([document["_id"] for document in documents])  # Delete existing documents to make room for new ones.
                actions = self._create_new_pages(content, sample_doc, text_field, index)
                success_count, errors = ed.bulk_add_raw(actions=actions, stats_only=False)
                return Response({"successfully_updated": success_count, "errors": errors})
            else:
                return Response(f"Could not find the id field withing the document!", status=status.HTTP_400_BAD_REQUEST)

        return Response(f"Could not find document with the id!", status=status.HTTP_400_BAD_REQUEST)


class DocumentImportView(GenericAPIView):
    serializer_class = InsertDocumentsSerializer
    permission_classes = (ProjectAllowed, permissions.IsAuthenticated)


    @staticmethod
    def get_new_index_name(project_id: int):
        index_name = f"texta-{DEPLOY_KEY}-import-project-{project_id}"
        return index_name


    def _normalize_missing_index_values(self, documents: List[dict], project_id: int):
        index_name = DocumentImportView.get_new_index_name(project_id)
        new_index = False
        for document in documents:
            document["_index"] = index_name
            document["_type"] = index_name
            new_index = True
        return documents, index_name, new_index


    def _split_documents_per_index(self, allowed_indices: List[str], documents: List[dict]):
        correct_permissions_indices = []
        failed_permissions_indices = []
        missing_indices = []

        for document in documents:
            index = document["_index"]
            if index is None:
                missing_indices.append(document)
            elif index in allowed_indices:
                correct_permissions_indices.append(document)
            else:
                failed_permissions_indices.append(document)

        return correct_permissions_indices, failed_permissions_indices, missing_indices


    def _split_text(self, documents: List[dict], fields: List[str]):
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
                            "_type": document["_index"],
                            "_source": content
                        })
                else:
                    container.append(document)
        return container


    def post(self, request, pk: int):
        # Synchronize indices between Toolkit and Elastic
        ed = ElasticDocument(index=None)
        ed.core.syncher()

        # Validate payload and project permissions.
        serializer: InsertDocumentsSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=pk)
        if request.user not in project.users.all():
            raise PermissionDenied("You do not have permissions for this project!")

        # Split indices on whether they have index access or lack any index details at all.
        documents = serializer.validated_data["documents"]
        split_fields = serializer.validated_data["split_text_in_fields"]
        indices = project.get_indices()
        correct_actions, failed_actions, missing_actions = self._split_documents_per_index(indices, documents)
        missing_actions, index_name, has_new_index = self._normalize_missing_index_values(missing_actions, project.pk)
        split_actions = self._split_text(correct_actions + missing_actions, split_fields)

        if has_new_index:
            index, is_created = Index.objects.get_or_create(name=index_name, is_open=True)
            project.indices.add(index)

        # Send the documents to Elasticsearch.
        success_count, errors = ed.bulk_add_raw(actions=split_actions, stats_only=False)
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
        project: Project = get_object_or_404(Project, pk=pk)
        if request.user not in project.users.all():
            raise PermissionDenied(f"User '{request.user.username}' does not have access to this project!")

        if index not in project.get_indices():
            raise PermissionDenied(f"You do not have access to this index!")

        ed = ElasticDocument(index)
        document = ed.get(document_id)
        if not document:
            raise NotFound(f"Could not find document with ID '{document_id}' from index '{index}'!")
        return Response(document)


    # TODO Add exception handling for missing documents.
    def delete(self, request, pk: int, index: str, document_id: str):
        project: Project = get_object_or_404(Project, pk=pk)
        if request.user not in project.users.all():
            raise PermissionDenied(f"User '{request.user.username}' does not have access to this project!")

        if index not in project.get_indices():
            raise PermissionDenied(f"You do not have access to this index!")

        ed = ElasticDocument(index)
        document = ed.delete(doc_id=document_id)
        return Response(document)


    # TODO Add exception handling for missing document.
    def patch(self, request, pk: int, index: str, document_id: str):
        project: Project = get_object_or_404(Project, pk=pk)
        if request.user not in project.users.all():
            raise PermissionDenied(f"User '{request.user.username}' does not have access to this project!")

        if index not in project.get_indices():
            raise PermissionDenied(f"You do not have access to this index!")

        try:
            ed = ElasticDocument(index)
            document = ed.update(index=index, doc_type=index, doc_id=document_id, doc=request.data)
            return Response(document)
        except elasticsearch.exceptions.RequestError as e:
            if e.error == "mapper_parsing_exception":
                return Response(e.info["error"]["root_cause"], status=status.HTTP_400_BAD_REQUEST)
