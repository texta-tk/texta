from rest_framework import serializers
from django.contrib.auth.models import User

from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.core.project.models import Project
from toolkit.core.choices import get_index_choices
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.tagger.models import Tagger


class ProjectResourcesSerializer(serializers.Serializer):
    embeddings = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    embedding_clusters = serializers.PrimaryKeyRelatedField(read_only=True, many=True)
    taggers = serializers.PrimaryKeyRelatedField(read_only=True, many=True)


class ProjectSerializer(serializers.ModelSerializer):
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    users = UserSerializer(many=True)
    resources = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices', 'resources')
        read_only_fields = ('owner', 'resources')

    def get_resources(self, obj):
        embeddings = Embedding.objects.filter(project=obj)
        embedding_clusters = EmbeddingCluster.objects.filter(project=obj)
        taggers = Tagger.objects.filter(project=obj)
        asd = {'taggers': taggers, 'embeddings': embeddings, 'embedding_clusters': embedding_clusters}
        return ProjectResourcesSerializer(instance=asd).data
