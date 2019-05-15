from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import action

from toolkit.core import permissions
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer
from toolkit.core.user_profile.serializers import UserProfileSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = (permissions.ProjectPermissions,)

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        current_user = self.get_current_user_id(self.request)
        user_obj = self.get_current_user_obj(self.request)
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # re-evaluate queryset on each request.
            queryset = queryset.all()
        if not user_obj.is_superuser:
            queryset = queryset[:].filter(owner=current_user) | queryset[:].filter(users=current_user)
        return queryset

    def get_current_user_id(self, request):
        return request.user.id

    def get_current_user_obj(self, request):
        return request.user

    # TODO permission_classes is just overwriting the viewset permission_classes here for tests
    # Something like IsOwnerOrIncludedUser would be useful
    @action(detail=True, methods=['get'], permission_classes=[])
    def activate_project(self, request, pk=None):
        obj = self.get_object()
        request.user.profile.activate_project(obj)
        return Response({'status': f'Project {pk} successfully activated.'}, status=status.HTTP_200_OK)

