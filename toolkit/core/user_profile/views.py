from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserProfileSerializer


class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserProfile.objects.all().order_by('-user__date_joined')
    serializer_class = UserProfileSerializer
