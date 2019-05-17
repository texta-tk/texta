from django.db.models.query import QuerySet
from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserProfileSerializer
from toolkit.core import permissions


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.all().order_by('-user__date_joined')
    serializer_class = UserProfileSerializer

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        current_user = self.request.user.id
        queryset = self.queryset
        if isinstance(queryset, QuerySet):
            # re-evaluate queryset on each request.
            queryset = queryset.all()
        if not self.request.user.is_superuser:
            queryset = queryset[:].filter(user_id=current_user)
        return queryset
