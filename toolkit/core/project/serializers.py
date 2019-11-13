from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.project.models import Project
from toolkit.core import choices as choices
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.tagger.models import Tagger
from toolkit.elastic.searcher import EMPTY_QUERY


class ProjectMultiTagSerializer(serializers.Serializer):
    text = serializers.CharField(help_text='Text to be tagged.')
    taggers = serializers.ListField(help_text='List of Tagger IDs to be used.',
                                    child=serializers.IntegerField())


class ProjectSearchByQuerySerializer(serializers.Serializer):
    query = serializers.JSONField(help_text='Query to search', default=EMPTY_QUERY)


class ProjectSimplifiedSearchSerializer(serializers.Serializer):
    match_text = serializers.CharField(help_text='String of list of strings to match.')
    match_type = serializers.ChoiceField(choices=choices.MATCH_CHOICES,
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
    operator = serializers.ChoiceField(choices=choices.OPERATOR_CHOICES,
        help_text=f'Operator to use in search.',
        default='must',
        required=False)
    size = serializers.IntegerField(default=10,
                                    help_text='Number of documents returned',
                                    required=False)


class ProjectGetFactsSerializer(serializers.Serializer):
    values_per_name = serializers.IntegerField(default=choices.DEFAULT_VALUES_PER_NAME,
        help_text=f'Number of fact values per fact name. Default: 10.')
    output_type = serializers.ChoiceField(choices=((True, 'fact names with values'), (False, 'fact names without values')),
                                          help_text=f'Include fact values in output. Default: True', default=True)


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(required=False, queryset=User.objects.all())
    owner_username = serializers.CharField(source='owner.username', read_only=True)

    indices = serializers.ListField(default=[], child=serializers.CharField())
    users = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail', queryset=User.objects.all(),)
    resources = serializers.SerializerMethodField()


    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices', 'resources', 'owner_username')
        read_only_fields = ('resources',)


    def get_resources(self, obj):
        request = self.context.get('request')
        base_url = request.build_absolute_uri(f'/projects/{obj.id}/')
        resource_dict = {}
        for resource_name in ('lexicons', 'reindexer', 'searches', 'embeddings', 'embedding_clusters', 'taggers', 'tagger_groups', 'torchtaggers'):
            resource_dict[resource_name] = f'{base_url}{resource_name}/'
        return resource_dict


class ProjectSuggestFactValuesSerializer(serializers.Serializer):
    limit = serializers.IntegerField(default=choices.DEFAULT_VALUES_PER_NAME,
        help_text=f'Number of suggestions. Default: {choices.DEFAULT_SUGGESTION_LIMIT}.')
    startswith = serializers.CharField(help_text=f'The string to autocomplete fact values with.', allow_blank=True)
    fact_name = serializers.CharField(help_text='Fact name from which to suggest values.')


class ProjectSuggestFactNamesSerializer(serializers.Serializer):
    limit = serializers.IntegerField(default=choices.DEFAULT_VALUES_PER_NAME,
        help_text=f'Number of suggestions. Default: {choices.DEFAULT_SUGGESTION_LIMIT}.')
    startswith = serializers.CharField(help_text=f'The string to autocomplete fact names with.', allow_blank=True)


class ProjectGetSpamSerializer(serializers.Serializer):
    target_field = serializers.CharField(required=True, help_text="Name of the Elasticsearch field you want to use for analysis.")
    from_date = serializers.CharField(default="now-1h", help_text="Lower threshold for limiting the date range. Accepts timestamps and Elasticsearch date math.")
    to_date = serializers.CharField(default="now", help_text="Upper threshold for limiting the date range. Accepts timestamps and Elasticsearch date math.")
    date_field = serializers.CharField(required=True, help_text="Name of the Elasticsearch field you want to use to limit the date range.")
    aggregation_size = serializers.IntegerField(min_value=1, max_value=10000, default=10, help_text="Number of how many items should be returned per aggregation.")
    min_doc_count = serializers.IntegerField(min_value=1, default=10, help_text="Number to set the minimum document matches that are returned.")
    common_feature_fields = serializers.ListField(child=serializers.CharField(), help_text="Elasticsearch field names to match common patterns.")
