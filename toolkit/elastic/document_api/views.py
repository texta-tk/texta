# Create your views here.
import json
from typing import List

import elasticsearch
import rest_framework.filters as drf_filters
import texta_elastic
from django_filters import rest_framework as filters
from elasticsearch_dsl import Q, Search
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from texta_tools.text_splitter import TextSplitter

from toolkit.core.project.models import Project
from toolkit.elastic.document_api.models import DeleteFactsByQueryTask, EditFactsByQueryTask
from toolkit.elastic.document_api.serializers import DeleteFactsByQuerySerializer, EditFactsByQuerySerializer, FactsSerializer, InsertDocumentsSerializer, UpdateFactsSerializer, UpdateSplitDocumentSerializer
from toolkit.elastic.document_importer.serializers import InsertDocumentsSerializer, UpdateSplitDocumentSerializer
from toolkit.elastic.index.models import Index
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed, ProjectEditAccessAllowed
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import DEPLOY_KEY, TEXTA_TAGS_KEY
from toolkit.view_constants import BulkDelete


def validate_index_and_project_perms(request, pk, index):
    project: Project = get_object_or_404(Project, pk=pk)
    if request.user not in project.users.all():
        raise PermissionDenied(f"User '{request.user.username}' does not have access to this project!")

    if index not in project.get_indices():
        raise PermissionDenied(f"You do not have access to this index!")


class DocumentImportView(GenericAPIView):
    serializer_class = InsertDocumentsSerializer
    permission_classes = (ProjectEditAccessAllowed, permissions.IsAuthenticated)


    @staticmethod
    def get_new_index_name(project_id: int):
        index_name = f"texta-{DEPLOY_KEY}-import-project-{project_id}"
        return index_name


    def _normalize_missing_index_values(self, documents: List[dict], project_id: int):
        index_name = DocumentImportView.get_new_index_name(project_id)
        new_index = False
        for document in documents:
            document["_index"] = index_name
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
        # Synchronize indices between Toolkit and Elastic
        ed = ElasticDocument(index=None)

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


class UpdateFactsView(GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UpdateFactsSerializer


    def post(self, request, pk: int, index: str, document_id: str):
        validate_index_and_project_perms(request, pk, index)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            ed = ElasticDocument(index)
            document = ed.get(document_id, fields=[TEXTA_TAGS_KEY])
            if not document:
                raise NotFound(f"Could not find document with ID '{document_id}' from index '{index}'!")
            document = document.get("_source")
            target_facts = serializer.validated_data.get("target_facts", [])
            resulting_fact = serializer.validated_data.get("resulting_fact")
            existing_facts = document.get(TEXTA_TAGS_KEY, [])
            for index_count, existing_fact in enumerate(existing_facts):
                for fact in target_facts:
                    if fact.items() <= existing_fact.items():
                        existing_facts[index_count] = resulting_fact
            document[TEXTA_TAGS_KEY] = existing_facts
            ed.update(index, document_id, doc=document)
            return Response({"message": f"Edited given facts from document with the ID of {document_id}!"})


class DeleteFactsView(GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = FactsSerializer


    def post(self, request, pk: int, index: str, document_id: str):
        validate_index_and_project_perms(request, pk, index)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            ed = ElasticDocument(index)
            document = ed.get(document_id, fields=[TEXTA_TAGS_KEY])
            if not document:
                raise NotFound(f"Could not find document with ID '{document_id}' from index '{index}'!")

            document = document.get("_source")
            target_facts = serializer.validated_data.get("facts", [])
            existing_facts = document.get(TEXTA_TAGS_KEY, [])

            new_facts = []
            for index_count, existing_fact in enumerate(existing_facts):
                for fact in target_facts:
                    if not (fact.items() <= existing_fact.items()):
                        new_facts.append(existing_fact)

            document[TEXTA_TAGS_KEY] = new_facts
            ed.update(index, document_id, doc=document)
            return Response({"message": f"Removed given facts from document with the ID of {document_id}!"})


class AddFactsView(GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = FactsSerializer


    def post(self, request, pk: int, index: str, document_id: str):
        validate_index_and_project_perms(request, pk, index)
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            ed = ElasticDocument(index)
            document = ed.get(document_id, fields=[TEXTA_TAGS_KEY])
            if not document:
                raise NotFound(f"Could not find document with ID '{document_id}' from index '{index}'!")

            document = document.get("_source")
            facts = serializer.validated_data.get("facts", [])
            existing_facts = document.get(TEXTA_TAGS_KEY, [])
            new_facts = ed.remove_duplicate_facts(facts + existing_facts)

            document[TEXTA_TAGS_KEY] = new_facts
            ed.update(index, document_id, doc=document)
            return Response({"message": f"Added given facts from document with the ID of {document_id}!"})


class DeleteFactsByQueryViewset(viewsets.ModelViewSet, BulkDelete):
    serializer_class = DeleteFactsByQuerySerializer
    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = (
        'id', 'author__username', 'description', 'tasks__time_started', 'tasks__time_completed', 'tasks__status')
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )


    def get_queryset(self):
        return DeleteFactsByQueryTask.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)
        facts = serializer.validated_data["facts"]
        query = serializer.validated_data["query"]

        serializer.validated_data.pop("indices")

        worker: DeleteFactsByQueryTask = serializer.save(
            author=self.request.user,
            project=project,
            query=json.dumps(query, ensure_ascii=False),
            facts=json.dumps(facts, ensure_ascii=False)
        )
        for index in Index.objects.filter(name__in=indices, is_open=True):
            worker.indices.add(index)
        worker.process()


class EditFactsByQueryViewset(viewsets.ModelViewSet, BulkDelete):
    serializer_class = EditFactsByQuerySerializer
    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    ordering_fields = (
        'id', 'author__username', 'description', 'tasks__time_started', 'tasks__time_completed', 'tasks__status')
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )


    def get_queryset(self):
        return EditFactsByQueryTask.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)
        target_facts = serializer.validated_data["target_facts"]
        resulting_fact = serializer.validated_data["fact"]
        query = serializer.validated_data["query"]

        serializer.validated_data.pop("indices")

        worker: EditFactsByQueryTask = serializer.save(
            author=self.request.user,
            project=project,
            query=json.dumps(query, ensure_ascii=False),
            target_facts=json.dumps(target_facts, ensure_ascii=False),
            fact=json.dumps(resulting_fact, ensure_ascii=False)
        )
        for index in Index.objects.filter(name__in=indices, is_open=True):
            worker.indices.add(index)
        worker.process()


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
