from django.db.models.query import QuerySet
from django.http import HttpResponse, Http404
from django.shortcuts import render
from django.contrib.auth.models import User
from toolkit.core.project.models import Project
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.permissions.project_permissions import IsSuperUser



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

    @action(detail=True, methods=['get', 'post'], permission_classes=[IsSuperUser])
    def assign_superuser(self, request, pk=None):
        user = User.objects.get(id=self.kwargs['pk'])
        user.is_superuser ^= True   # toggle
        user.save()
        if user.is_superuser:
            return Response({"detail": "Superuser status assigned"}, status=status.HTTP_200_OK)
        return Response({"detail": "Superuser status removed"}, status=status.HTTP_200_OK)




