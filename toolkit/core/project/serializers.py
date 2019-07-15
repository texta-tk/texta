from rest_framework import serializers
from django.contrib.auth.models import User

from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.core.project.models import Project
from toolkit.core.choices import get_index_choices
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.tagger.models import Tagger

DEFAULT_VALUES_PER_NAME = 10

class GetFactsSerializer(serializers.Serializer):
    values_per_name = serializers.IntegerField(default=DEFAULT_VALUES_PER_NAME,
        help_text=f'Number of fact values per fact name. Default: 10.')
    output_type = serializers.ChoiceField(choices=((True, 'fact names with values'), (False, 'fact names without values')),
        help_text=f'Include fact values in output. Default: True', default=True)


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    users = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail', queryset=User.objects.all())
    resources = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices', 'resources')
        read_only_fields = ('owner', 'resources')

    def get_resources(self, obj):
        request = self.context.get('request')
        base_url = request.build_absolute_uri(f'/projects/{obj.id}/')
        resource_dict = {}
        for resource_name in ('embeddings', 'embedding_clusters', 'taggers', 'tagger_groups', 'neurotaggers'):
            resource_dict[resource_name] = f'{base_url}{resource_name}/'
        return resource_dict
