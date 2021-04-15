from typing import List

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import serializers

from toolkit.core import choices as choices
from toolkit.core.project.models import Project
from toolkit.core.project.validators import check_if_in_elastic
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.elastic.index.serializers import IndexSerializer


class ExportSearcherResultsSerializer(serializers.Serializer):
    indices = serializers.ListField(child=serializers.CharField(), default=[])
    query = serializers.JSONField(help_text="Which query results to fetch.", default=EMPTY_QUERY)


class ProjectSearchByQuerySerializer(serializers.Serializer):
    query = serializers.JSONField(help_text='Query to search', default=EMPTY_QUERY)
    indices = serializers.ListField(default=None,
                                    required=False,
                                    help_text='Indices in project to apply query on. Default: empty (all indices in project)')
    output_type = serializers.ChoiceField(choices=choices.OUTPUT_CHOICES,
                                          default=None,
                                          required=False,
                                          help_text='Document response type')


class ProjectDocumentSerializer(serializers.Serializer):
    indices = serializers.ListField(default=None,
                                    required=False,
                                    help_text='Indices to search in')
    doc_id = serializers.CharField(required=True, help_text='document id to search for')


class ProjectSimplifiedSearchSerializer(serializers.Serializer):
    match_text = serializers.CharField(help_text='String of list of strings to match.')
    match_type = serializers.ChoiceField(
        choices=choices.MATCH_CHOICES,
        help_text='Match type to apply. Default: match.',
        default='word',
        required=False
    )
    match_indices = serializers.ListField(
        child=serializers.CharField(),
        help_text='Match from specific indices in project. Default: EMPTY - all indices are used.',
        default=None,
        required=False
    )
    match_fields = serializers.ListField(
        child=serializers.CharField(),
        help_text='Match from specific fields in project. Default: EMPTY - all fields are used.',
        default=None,
        required=False
    )
    operator = serializers.ChoiceField(
        choices=choices.OPERATOR_CHOICES,
        help_text=f'Operator to use in search.',
        default='must',
        required=False
    )
    size = serializers.IntegerField(
        default=10,
        help_text='Number of documents returned',
        required=False
    )


class ProjectGetFactsSerializer(serializers.Serializer):
    indices = IndexSerializer(many=True, default=[], help_text="Which indices to use for the fact search.")

    values_per_name = serializers.IntegerField(
        default=choices.DEFAULT_VALUES_PER_NAME,
        help_text=f'Number of fact values per fact name. Default: 10.'
    )
    output_type = serializers.ChoiceField(
        choices=((True, 'fact names with values'), (False, 'fact names without values')),
        help_text=f'Include fact values in output. Default: True', default=True
    )


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    title = serializers.CharField(required=True)
    indices = serializers.ListField(default=[], child=serializers.CharField(), source="get_indices", validators=[check_if_in_elastic])
    users = serializers.HyperlinkedRelatedField(many=True, view_name='user-detail', queryset=User.objects.all(), )
    author_username = serializers.CharField(source='author.username', read_only=True)
    resources = serializers.SerializerMethodField()


    def update(self, instance, validated_data):
        from toolkit.elastic.index.models import Index

        if "title" in validated_data:
            instance.title = validated_data["title"]
            instance.save()

        if "get_indices" in validated_data:
            ec = ElasticCore()
            ec.syncher()
            container = []
            for index_name in validated_data["get_indices"]:
                index, is_created = Index.objects.get_or_create(name=index_name)
                container.append(index)

            instance.indices.set(container)
            instance.save()

        if "users" in validated_data:
            instance.users.set(validated_data["users"])
            instance.save()

        return instance


    def create(self, validated_data):
        from toolkit.elastic.index.models import Index
        indices: List[str] = validated_data["get_indices"]
        title = validated_data["title"]
        users = validated_data["users"]
        author = self.context["request"].user
        # create object
        project = Project.objects.create(title=title, author=author)
        project.users.set(users)
        # only run if indices given as we might not have elastic running
        if indices:
            ec = ElasticCore()
            ec.syncher()
            for index_name in indices:
                index, is_created = Index.objects.get_or_create(name=index_name)
                project.indices.add(index)
        # save project
        project.save()
        return project


    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'author_username', 'users', 'indices', 'resources',)
        read_only_fields = ('author_username', 'resources',)


    def get_resources(self, obj):
        request = self.context.get('request')
        api_version = self.context["request"].version
        version_prefix = f'/api/{api_version}'
        base_url = request.build_absolute_uri(f'{version_prefix}/projects/{obj.id}/')
        resource_dict = {}

        if api_version == 'v2':
            resources = (
                'lexicons',
                'elastic/reindexer',
                'elastic/index_splitter',
                'elastic/dataset_imports',
                'elastic/face_analyzer',
                'elastic/scroll',
                'searches',
                'embeddings',
                'topic_analyzer',
                'taggers',
                'tagger_groups',
                'torchtaggers',
                'bert_taggers',
                'regex_taggers',
                'anonymizers',
                'regex_tagger_groups',
                'mlp_index',
                'lang_index',
                'evaluators'
            )
        elif api_version == 'v1':
            resources = (
                'lexicons',
                'reindexer',
                'index_splitter',
                'dataset_imports',
                'searches',
                'scroll',
                'clustering',
                'embeddings',
                'taggers',
                'tagger_groups',
                'torchtaggers',
                'bert_taggers',
                'regex_taggers',
                'anonymizers',
                'regex_tagger_groups',
                'mlp_index',
                'lang_index',
                'evaluators'
            )

        for resource_name in resources:
            resource_dict[resource_name] = f'{base_url}{resource_name}/'

        additional_urls = ['mlp_texts', 'mlp_docs']
        for item in additional_urls:
            view_url = reverse(f"{api_version}:{item}")
            resource_dict[item] = request.build_absolute_uri(view_url)

        importer_uri = reverse(f"{api_version}:document_import", kwargs={"pk": obj.id})
        resource_dict["document_import_api"] = request.build_absolute_uri(importer_uri)
        return resource_dict


class ProjectSuggestFactValuesSerializer(serializers.Serializer):
    limit = serializers.IntegerField(default=choices.DEFAULT_VALUES_PER_NAME,
                                     help_text=f'Number of suggestions. Default: {choices.DEFAULT_SUGGESTION_LIMIT}.')
    startswith = serializers.CharField(help_text=f'The string to autocomplete fact values with.', allow_blank=True)
    fact_name = serializers.CharField(help_text='Fact name from which to suggest values.')
    indices = serializers.ListField(child=serializers.CharField(), default=[], required=False, help_text="Which indices to use for the fact search.")


class CountIndicesSerializer(serializers.Serializer):
    indices = serializers.ListField(child=serializers.CharField(), default=[], help_text="Which indices to use for the count.")


class ProjectSuggestFactNamesSerializer(serializers.Serializer):
    limit = serializers.IntegerField(default=choices.DEFAULT_VALUES_PER_NAME,
                                     help_text=f'Number of suggestions. Default: {choices.DEFAULT_SUGGESTION_LIMIT}.')
    startswith = serializers.CharField(help_text=f'The string to autocomplete fact names with.', allow_blank=True)
    indices = IndexSerializer(many=True, default=[], help_text="Which indices to use for the fact search.")


class ProjectGetSpamSerializer(serializers.Serializer):
    target_field = serializers.CharField(required=True, help_text="Name of the Elasticsearch field you want to use for analysis.")
    from_date = serializers.CharField(default="now-1h", help_text="Lower threshold for limiting the date range. Accepts timestamps and Elasticsearch date math.")
    to_date = serializers.CharField(default="now", help_text="Upper threshold for limiting the date range. Accepts timestamps and Elasticsearch date math.")
    date_field = serializers.CharField(required=True, help_text="Name of the Elasticsearch field you want to use to limit the date range.")
    aggregation_size = serializers.IntegerField(min_value=1, max_value=10000, default=10, help_text="Number of how many items should be returned per aggregation.")
    min_doc_count = serializers.IntegerField(min_value=1, default=10, help_text="Number to set the minimum document matches that are returned.")
    common_feature_fields = serializers.ListField(child=serializers.CharField(), help_text="Elasticsearch field names to match common patterns.")
