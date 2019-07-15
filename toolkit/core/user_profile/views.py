from django.db.models.query import QuerySet
from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import viewsets

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserSerializer


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer

    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = queryset.filter(id=self.request.user.id)
        return queryset
