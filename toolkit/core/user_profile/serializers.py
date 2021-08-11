from django.contrib.auth.models import User
from rest_framework import serializers

from .models import UserProfile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('first_name', 'last_name', 'is_uaa_account', 'scopes', 'application',)
        read_only_fields = ('application', 'is_uaa_account', 'scopes')


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


    def update(self, instance, validated_data):
        instance = super(UserSerializer, self).update(instance, validated_data)
        # Because staff and superusers are interchangeable and some of DRF's built in
        # methods only check is_staff we keep them in sync when superuser is mentioned.
        if "is_superuser" in validated_data:
            instance.is_staff = instance.is_superuser

        instance.save()
        return instance


    class Meta:
        model = User

        fields = ('url', 'id', 'username', 'email', 'display_name', 'date_joined', 'last_login', 'is_superuser', 'profile')
        read_only_fields = ('username', 'email', 'display_name', 'date_joined', 'last_login', 'profile')
