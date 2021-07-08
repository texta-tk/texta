from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile
from ...serializer_constants import FieldParseSerializer


class ProfileSerializer(FieldParseSerializer, serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('first_name', 'last_name', 'application', 'scope',)
        read_only_fields = ('application', 'scope',)
        fields_to_parse = ("scope",)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    profile = ProfileSerializer(read_only=True)
    display_name = serializers.SerializerMethodField()


    def get_display_name(self, instance: User):
        first_name = instance.profile.first_name
        last_name = instance.profile.last_name
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        elif last_name:
            return last_name
        else:
            return instance.username


    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'display_name', 'date_joined', 'last_login', 'is_superuser', 'profile')
        read_only_fields = ('username', 'email', 'display_name', 'date_joined', 'last_login', 'profile')
