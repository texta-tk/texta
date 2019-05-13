from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.user_profile.models import UserProfile
from toolkit.core.user_profile.serializers import UserProfileSerializer

# Create your views here.
class UserProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = UserProfile.objects.all().order_by('-user__date_joined')
    serializer_class = UserProfileSerializer
