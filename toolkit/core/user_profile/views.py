from django.db.models.query import QuerySet
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.contrib.auth.models import User
from toolkit.core.project.models import Project
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserSerializer



class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    list: Returns list of users.
    read: Returns user details by id.
    """

    serializer_class = UserSerializer
    # Disable default pagination
    pagination_class = None

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
