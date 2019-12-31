from django.db.models.query import QuerySet
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.contrib.auth.models import User
from toolkit.core.project.models import Project
from rest_framework import viewsets, permissions, status, mixins
from rest_framework.response import Response
from rest_framework.decorators import action

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.permissions.project_permissions import UserIsAdminOrReadOnly


class UserViewSet(mixins.RetrieveModelMixin,
                  mixins.ListModelMixin,
                  mixins.UpdateModelMixin,
                  viewsets.GenericViewSet):
    """
    list: Returns list of users.
    read: Returns user details by id.
    update: can update superuser status.
    """

    serializer_class = UserSerializer
    # Disable default pagination
    pagination_class = None
    permission_classes = (UserIsAdminOrReadOnly,)

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = queryset.filter(id=self.request.user.id)
        return queryset
