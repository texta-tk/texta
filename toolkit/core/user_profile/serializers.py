from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class ProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = UserProfile
        fields = ('application', 'scope',)
        read_only_fields = ('application', 'scope',)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'date_joined', 'is_superuser', 'last_login', 'profile')
        read_only_fields = ('username', 'email', 'date_joined', 'last_login', 'profile')

