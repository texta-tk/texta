from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ('application',)
        read_only_fields = ('application',)


class UserSerializer(serializers.HyperlinkedModelSerializer):
    profile = ProfileSerializer(read_only=True)


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
        fields = ('url', 'id', 'username', 'email', 'date_joined', 'is_superuser', 'last_login', 'profile')
        read_only_fields = ('username', 'email', 'date_joined', 'last_login', 'profile')
