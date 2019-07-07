from rest_framework import serializers
from django.contrib.auth.models import User

from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.core.project.models import Project
from toolkit.core.choices import get_index_choices

class ProjectSerializer(serializers.ModelSerializer):
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    users = UserSerializer(many=True)

    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices')
        read_only_fields = ('owner', )
