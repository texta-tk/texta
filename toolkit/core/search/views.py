from rest_framework import viewsets, status, permissions
from rest_framework.response import Response

from toolkit.permissions.project_permissions import ProjectAllowed
from toolkit.core.search.models import Search
from toolkit.core.project.models import Project
from toolkit.core.search.serializers import SearchSerializer
from toolkit.view_constants import BulkDelete

class SearchViewSet(viewsets.ModelViewSet, BulkDelete):
    """
    list:
    Returns list of Search objects.

    read:
    Return Search object by id.

    create:
    Creates Search object.

    update:
    Updates entire Search object.

    partial_update:
    Performs partial update on Search object.

    delete:
    Deletes Search object.
    """
    pagination_class = None
    serializer_class = SearchSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectAllowed,
    )

    def perform_create(self, serializer):
        serializer.save(
            author=self.request.user,
            project=Project.objects.get(id=self.kwargs['project_pk']),
        )

    def get_queryset(self):
        return Search.objects.filter(project=self.kwargs['project_pk'])

    def create(self, request, *args, **kwargs):
        serializer = SearchSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
