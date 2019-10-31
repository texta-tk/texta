from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.choices import MATCH_CHOICES, OPERATOR_CHOICES, get_index_choices
from toolkit.core.project.models import Project
from toolkit.elastic.searcher import EMPTY_QUERY


DEFAULT_VALUES_PER_NAME = 10


class ProjectMultiTagSerializer(serializers.Serializer):
    text = serializers.CharField(help_text='Text to be tagged.')
    taggers = serializers.ListField(help_text='List of Tagger IDs to be used.',
                                    child=serializers.IntegerField())


class ProjectSearchByQuerySerializer(serializers.Serializer):
    query = serializers.JSONField(help_text='Query to search', default=EMPTY_QUERY)


class ProjectSimplifiedSearchSerializer(serializers.Serializer):
    match_text = serializers.CharField(help_text='String of list of strings to match.')
    match_type = serializers.ChoiceField(choices=MATCH_CHOICES,
                                         help_text='Match type to apply. Default: match.',
                                         default='word',
                                         required=False)
    match_indices = serializers.ListField(child=serializers.CharField(),
                                          help_text='Match from specific indices in project. Default: EMPTY - all indices are used.',
                                          default=None,
                                          required=False)
    match_fields = serializers.ListField(child=serializers.CharField(),
                                         help_text='Match from specific fields in project. Default: EMPTY - all fields are used.',
                                         default=None,
                                         required=False)
    operator = serializers.ChoiceField(choices=OPERATOR_CHOICES,
                                       help_text=f'Operator to use in search.',
                                       default='must',
                                       required=False)
    size = serializers.IntegerField(default=10,
                                    help_text='Number of documents returned',
                                    required=False)


class ProjectGetFactsSerializer(serializers.Serializer):
    values_per_name = serializers.IntegerField(default=DEFAULT_VALUES_PER_NAME,
                                               help_text=f'Number of fact values per fact name. Default: 10.')
    output_type = serializers.ChoiceField(choices=((True, 'fact names with values'), (False, 'fact names without values')),
                                          help_text=f'Include fact values in output. Default: True', default=True)


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(required=False, queryset=User.objects.all())
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    users = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail', queryset=User.objects.all(), )
    resources = serializers.SerializerMethodField()


    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices', 'resources', 'owner_username')
        read_only_fields = ('resources',)


    def get_resources(self, obj):
        request = self.context.get('request')
        base_url = request.build_absolute_uri(f'/projects/{obj.id}/')
        resource_dict = {}
        for resource_name in ('lexicons', 'searches', 'embeddings', 'embedding_clusters', 'taggers', 'tagger_groups', 'neurotaggers'):
            resource_dict[resource_name] = f'{base_url}{resource_name}/'
        return resource_dict


class ProjectSpamSerializer(serializers.Serializer):
    target_field = serializers.CharField(required=True)
    from_date = serializers.CharField(default="now")
    to_date = serializers.CharField(default="now-1h")
    date_field = serializers.CharField(required=True)
    aggregation_size = serializers.IntegerField(min_value=1, max_value=10000, default=10)
    min_doc_count = serializers.IntegerField(min_value=1, default=10)
    all_fields = serializers.ListField(required=True, child=serializers.DictField(), min_length=1)
