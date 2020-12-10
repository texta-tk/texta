# Create your views here.
import elasticsearch
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.generics import GenericAPIView, get_object_or_404
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.document_importer.serializers import InsertDocumentsSerializer
from toolkit.elastic.document import ElasticDocument
from toolkit.permissions.project_permissions import ProjectAllowed


class DocumentImportView(GenericAPIView):
    serializer_class = InsertDocumentsSerializer
    permission_classes = (ProjectAllowed, permissions.IsAuthenticated)


    def post(self, request, pk: int):
        serializer: InsertDocumentsSerializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = get_object_or_404(Project, pk=pk)
        indices = set(project.get_indices())
        if request.user not in project.users.all():
            raise PermissionDenied("You do not have permissions for this project!")

        actions = serializer.validated_data["documents"]
        failed_permissions = []
        valid_actions = []

        for action in actions:
            if action["_index"] in indices:
                valid_actions.append(action)
            else:
                failed_permissions.append(action)

        ed = ElasticDocument(index=None)
        success_count, errors = ed.bulk_add_raw(actions=valid_actions, stats_only=False)
        return Response(
            {
                "successfully_indexed": success_count,
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
