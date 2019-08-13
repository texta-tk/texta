from django.db.models.query import QuerySet
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.contrib.auth.models import User
from toolkit.core.project.models import Project
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.core import permissions as core_permissions


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer

    """
    User permissions are contained in this class. A non-superuser can view itself and users who are members in projects the user owns.
    """

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        current_user = self.request.user
        projects = Project.objects.filter(owner=current_user)
        if not current_user.is_superuser:
            queryset = (queryset.filter(id=self.request.user.id) | queryset.filter(project_users__in=projects)).distinct()
        return queryset

    def handle_exception(self, exc):
        if isinstance(exc, Http404):
            return Response({'data': 'Insufficient permissions for this resource.'},
                            status=status.HTTP_404_NOT_FOUND)

        return super(ProjectDetails, self).handle_exception(exc)
