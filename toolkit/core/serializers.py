from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.models import Project, Profile
from toolkit.datasets.serializers import DatasetSerializer


class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ('projects', )

class UserSerializer(serializers.HyperlinkedModelSerializer):
    profile = ProfileSerializer(read_only=True)
    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'profile')


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    owner = UserSerializer(read_only=True)
    project_datasets = DatasetSerializer(many=True, read_only=True)
    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'project_datasets')