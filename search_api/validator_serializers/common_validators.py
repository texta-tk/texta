from account.models import Profile
from rest_framework import serializers


def validate_auth_token(auth_token: str):
    authenticated_token = Profile.objects.filter(auth_token=auth_token).first()
    if not authenticated_token:
        raise serializers.ValidationError('Failed to authenticate token.')

