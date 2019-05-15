from django.db.models.query import QuerySet
from rest_framework import viewsets

from toolkit.core import permissions
from toolkit.core.project.models import Project
from toolkit.core.project.serializers import ProjectSerializer


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
