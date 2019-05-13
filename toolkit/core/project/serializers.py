from rest_framework import serializers

from toolkit.core.project.models import Project
from toolkit.core.choices import get_index_choices

class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    from toolkit.embedding.serializers import EmbeddingSerializer
    indices = serializers.MultipleChoiceField(choices=get_index_choices())

    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices')
