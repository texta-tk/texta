import json
import re
from collections import OrderedDict
from json import JSONDecodeError

from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.choice_constants import DEFAULT_BULK_SIZE, DEFAULT_ES_TIMEOUT, DEFAULT_MAX_CHUNK_BYTES
from toolkit.core.project.models import Project
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.validators import check_for_existence
# Helptext constants to ensure consistent values inside Toolkit.
from toolkit.settings import ES_BULK_SIZE_MAX, ES_TIMEOUT_MAX


BULK_SIZE_HELPTEXT = "How many documents should be sent into Elasticsearch in a single batch for update."
ES_TIMEOUT_HELPTEXT = "How many seconds should be allowed for the the update request to Elasticsearch."
DESCRIPTION_HELPTEXT = "Description of the task to distinguish it from others."
QUERY_HELPTEXT = "Elasticsearch query for subsetting in JSON format"
FIELDS_HELPTEXT = "Which fields to parse the content from."
PROJECT_HELPTEXT = "Which Project this item belongs to."
INDICES_HELPTEXT = "Which indices to query from Elasticsearch"


class EmptySerializer(serializers.Serializer):
    pass


class ProjectResourceUrlSerializer():
    '''For project serializers which need to construct the HyperLinked URL'''


    def get_url(self, obj):
        request = self.context['request']
        path = re.sub(r'\d+\/*$', '', request.path)
        resource_url = request.build_absolute_uri(f'{path}{obj.id}/')
        return resource_url


    def get_plot(self, obj):
        request = self.context['request']
        resource_url = request.build_absolute_uri(f'/{obj.plot}')
        return resource_url


class FieldsValidationSerializerMixin:

    def validate_fields(self, value):
        """ check if selected fields are present in the project and raise error on None
            if no "fields" field is declared in the serializer, no validation
            to write custom validation for serializers with FieldParseSerializer, simply override validate_fields in the project serializer"""
        project_id = self.context['view'].kwargs['project_pk']
        project_obj = Project.objects.prefetch_related("users", "administrators", "indices").select_related("author", "author__profile").get(id=project_id)
        project_fields = set(project_obj.get_elastic_fields(path_list=True))
        if not value or not set(value).issubset(project_fields):
            raise serializers.ValidationError(f'Entered fields not in current project fields: {project_fields}')
        return value


class FieldValidationSerializerMixin:


    def validate_field(self, value):
        project_id = self.context['view'].kwargs['project_pk']
        project_obj = Project.objects.prefetch_related("users", "administrators", "indices").select_related("author", "author__profile").get(id=project_id)
        project_fields = set(project_obj.get_elastic_fields(path_list=True))
        if not value or not {value}.issubset(project_fields):
            raise serializers.ValidationError(f'Entered field not in current project fields: {project_fields}')
        return value


class FieldParseSerializer(FieldsValidationSerializerMixin):
    """
    For serializers that need to override to_representation and parse fields
    Serializers overriden with FieldParseSerializer will validate, if field input
    """


    def to_representation(self, instance):
        # self is the parent class obj in this case
        result = super(FieldParseSerializer, self).to_representation(instance)

        if instance.__class__.__name__ in ["Project", "UserProfile"]:
            model_obj = instance
        else:
            model_obj = self.Meta.model.objects.get(id=instance.id)

        fields_to_parse = self.Meta.fields_to_parse
        for field in fields_to_parse:
            if getattr(model_obj, field):
                try:
                    result[field] = json.loads(getattr(model_obj, field))
                except JSONDecodeError:
                    result[field] = getattr(model_obj, field)
        return OrderedDict([(key, result[key]) for key in result])


class ProjectResourceBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.JSONField(help_text='JSON list of ints. WARNING: use the "Raw data" form for proper JSON serialization.')


class GeneralTextSerializer(serializers.Serializer):
    text = serializers.CharField()


class ProjectResourceImportModelSerializer(serializers.Serializer):
    file = serializers.FileField()


class FeedbackSerializer(serializers.Serializer):
    feedback_id = serializers.CharField()
    correct_result = serializers.CharField()


class ProjectFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get("request", None)
        view = self.context.get("view", None)
        queryset = super(ProjectFilteredPrimaryKeyRelatedField, self).get_queryset()
        if not request or not queryset:
            return None
        return queryset.filter(project=view.kwargs["project_pk"])


class ProjectFasttextFilteredPrimaryKeyRelatedField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        request = self.context.get("request", None)
        view = self.context.get("view", None)
        queryset = super(ProjectFasttextFilteredPrimaryKeyRelatedField, self).get_queryset()
        if not request or not queryset:
            return None
        return queryset.filter(project=view.kwargs["project_pk"]).filter(embedding_type="FastTextEmbedding")


# Subclassing serializers.Serializer is necessary for some magical reason,
# without it, the ModelSerializers behavior takes precedence no matter how you subclass it.
class IndicesSerializerMixin(serializers.Serializer):
    indices = IndexSerializer(
        many=True,
        default=[],
        help_text=INDICES_HELPTEXT,
        validators=[
            check_for_existence
        ]
    )


class ElasticScrollMixIn(serializers.Serializer):
    es_timeout = serializers.IntegerField(
        default=DEFAULT_ES_TIMEOUT,
        help_text=f"Elasticsearch scroll timeout in minutes. Default:{DEFAULT_ES_TIMEOUT}."
    )
    bulk_size = serializers.IntegerField(
        min_value=1,
        max_value=10000,
        default=DEFAULT_BULK_SIZE,
        help_text=f"How many documents should be sent towards Elasticsearch at once. Default:{DEFAULT_BULK_SIZE}."
    )
    max_chunk_bytes = serializers.IntegerField(
        min_value=1,
        default=DEFAULT_MAX_CHUNK_BYTES,
        help_text=f"Data size in bytes that Elasticsearch should accept to prevent Entity Too Large errors. Default:{DEFAULT_MAX_CHUNK_BYTES}."
    )


class ToolkitTaskSerializer(IndicesSerializerMixin, FieldsValidationSerializerMixin):
    description = serializers.CharField(max_length=100, help_text=DESCRIPTION_HELPTEXT)
    author = UserSerializer(read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False, help_text=FIELDS_HELPTEXT)
    query = serializers.JSONField(required=False, help_text=QUERY_HELPTEXT, default=json.dumps(EMPTY_QUERY, ensure_ascii=False))

    bulk_size = serializers.IntegerField(default=100, min_value=1, max_value=ES_BULK_SIZE_MAX, help_text=BULK_SIZE_HELPTEXT)
    es_timeout = serializers.IntegerField(default=10, min_value=1, max_value=ES_TIMEOUT_MAX, help_text=ES_TIMEOUT_HELPTEXT)
