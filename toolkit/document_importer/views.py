# Create your views here.
import string
from typing import List

import elasticsearch
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.document_importer.serializers import InsertDocumentsSerializer
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.models import Index
from toolkit.permissions.project_permissions import ProjectAllowed


class DocumentImportView(GenericAPIView):
    serializer_class = InsertDocumentsSerializer
    permission_classes = (ProjectAllowed, permissions.IsAuthenticated)


    @staticmethod
    def normalize_project_title(title: str):
        for char in string.punctuation:
            title = title.replace(char, '')

        title = title.lower()
        title = title.replace(" ", "_")
        title = title.strip()
        return title


    def _split_actions_per_permissions(self, actions: List[dict], indices: set):
        valid_actions = []
        failed_permissions = []
        for action in actions:
            if action["_index"] in indices:
                valid_actions.append(action)
            else:
                failed_permissions.append(action)
        return valid_actions, failed_permissions


    @staticmethod
    def get_new_index_name(title: str):
        normalized_title = DocumentImportView.normalize_project_title(title)
        index_name = f"{normalized_title}_imported"
        return index_name


    def _process_actions(self, project: Project, actions: List[dict]):
        index_name = DocumentImportView.get_new_index_name(title=project.title)
        index_processed = False
        new_index_created = False

        for action in actions:
            if action["_index"] is None or action["_type"] is None:
                if index_processed is False:
                    index, is_created = Index.objects.get_or_create(name=index_name)
                    project.indices.add(index)
                    index_processed = True
                    new_index_created = is_created

                action["_index"] = index_name
                action["_type"] = index_name

        return actions, index_name, new_index_created


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

        # Validate and process index permissions and documents.
        actions, index_name, new_index_created = self._process_actions(project, serializer.validated_data["documents"])
        indices = set(project.get_indices())
        created_indices = [index_name] if new_index_created else []
        valid_actions, failed_permissions = self._split_actions_per_permissions(actions, indices)

        # Send the documents to Elasticsearch.
        ed = ElasticDocument(index=None)
        success_count, errors = ed.bulk_add_raw(actions=valid_actions, stats_only=False)
        return Response(
            {
                "successfully_indexed": success_count,
                "created_indices": created_indices,
                "errors": errors,
                "failed_index_permissions": failed_permissions
            }
        )


class DocumentInstanceView(GenericAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = InsertDocumentsSerializer


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
