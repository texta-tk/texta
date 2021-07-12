from typing import List

from django.contrib.auth.models import User
from django.db import transaction
from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError

from toolkit.core import choices as choices
from toolkit.core.project.models import Project
from toolkit.core.project.validators import check_if_in_elastic
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.core.user_profile.validators import check_if_username_exist
from toolkit.elastic.index.models import Index
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.helper_functions import wrap_in_list


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


class HandleIndicesSerializer(serializers.Serializer):
    indices = serializers.PrimaryKeyRelatedField(many=True, queryset=Index.objects.filter(is_open=True), )
    # indices = IndexSerializer(many=True)


class HandleUsersSerializer(serializers.Serializer):
    # users = UserSerializer(many=True)
    users = serializers.PrimaryKeyRelatedField(many=True, queryset=User.objects.all(), )


class HandleProjectAdministratorsSerializer(serializers.Serializer):
    # project_admins = UserSerializer(many=True)
    project_admins = serializers.PrimaryKeyRelatedField(many=True, queryset=User.objects.all(), )


class ProjectSerializer(serializers.ModelSerializer):
    title = serializers.CharField(required=True)

    indices = IndexSerializer(many=True, required=False, read_only=True)
    indices_write = serializers.ListField(child=serializers.CharField(), write_only=True, default=[], validators=[check_if_in_elastic])

    users = UserSerializer(many=True, default=serializers.CurrentUserDefault(), read_only=True)
    users_write = serializers.ListField(child=serializers.CharField(validators=[check_if_username_exist]), write_only=True, default=[])

    administrators = UserSerializer(many=True, default=serializers.CurrentUserDefault(), read_only=True)
    administrators_write = serializers.ListField(child=serializers.CharField(validators=[check_if_username_exist]), write_only=True, default=[])

    author_username = serializers.CharField(source='author.username', read_only=True)
    resources = serializers.SerializerMethodField()
    resource_count = serializers.SerializerMethodField()

    # For whatever reason, it doesn't validate read-only fields, so we do it manually.
    def validate(self, data):
        if hasattr(self, 'initial_data'):
            read_only_keys = ["indices", "users", "administrators"]
            for key in read_only_keys:
                if key in self.initial_data:
                    raise ValidationError(f"Field: '{key}' is a read-only field, please use {key}_write instead!")
        return data


    def __enrich_payload_with_orm(self, base, data):
        author = self.context["request"].user
        fields = ["users_write", "administrators_write"]
        for field in fields:
            usernames = data.get(field, None)
            if not usernames:
                base[field] = [author]
            else:
                base[field] = list(User.objects.filter(username__in=usernames))
        return base


    def to_internal_value(self, data):
        base = super(ProjectSerializer, self).to_internal_value(data)
        base = self.__enrich_payload_with_orm(base, data)
        return base


    def update(self, instance: Project, validated_data: dict):
        if "title" in validated_data:
            instance.title = validated_data["title"]
            instance.save()

        return instance


    def create(self, validated_data):
        from toolkit.elastic.index.models import Index
        indices: List[str] = validated_data.get("indices_write", None)
        title = validated_data["title"]
        users = wrap_in_list(validated_data["users_write"])
        administrators = wrap_in_list(validated_data["administrators_write"])
        author = self.context["request"].user

        if indices and not author.is_superuser:
            raise PermissionDenied("Non-superusers can not create projects with indices defined!")

        # create object
        with transaction.atomic():
            project = Project.objects.create(title=title, author=author)
            project.users.add(*users, *administrators, author)
            project.administrators.add(*administrators, author)  # All admins are also users.

            # only run if indices given as we might not have elastic running
            if indices:
                ec = ElasticCore()
                ec.syncher()
                for index_name in indices:
                    index, is_created = Index.objects.get_or_create(name=index_name)
                    project.indices.add(index)

        return project


    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'author_username', 'administrators_write', 'administrators', 'users', 'users_write', 'indices', 'indices_write', 'resources', 'resource_count',)
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
                'elastic/search_query_tagger',
                'elastic/search_fields_tagger',
                'elastic/scroll',
                'elastic/apply_analyzers',
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
                'evaluators',
                'summarizer_index'
            )
        elif api_version == 'v1':
            resources = (
                'lexicons',
                'reindexer',
                'search_query_tagger',
                'search_fields_tagger',
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
                'evaluators',
                'summarizer_index',
                'apply_analyzers'
            )

        for resource_name in resources:
            resource_dict[resource_name] = f'{base_url}{resource_name}/'

        additional_urls = ['mlp_texts', 'mlp_docs', 'summarizer_summarize']
        for item in additional_urls:
            view_url = reverse(f"{api_version}:{item}")
            resource_dict[item] = request.build_absolute_uri(view_url)

        importer_uri = reverse(f"{api_version}:document_import", kwargs={"pk": obj.id})
        resource_dict["document_import_api"] = request.build_absolute_uri(importer_uri)
        return resource_dict


    def get_resource_count(self, obj):
        return sum(obj.get_resource_counts().values())


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


class UaaGroupIdSerializer(serializers.Serializer):
    group_id = serializers.CharField(required=True, help_text="Unique identifier of a group inside UAA.")