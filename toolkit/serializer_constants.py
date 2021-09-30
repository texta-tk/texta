import json
import re
from collections import OrderedDict

from rest_framework import serializers

from toolkit.core.project.models import Project
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.validators import check_for_existence

# Helptext constants to ensure consistent values inside Toolkit.
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


class FieldValidationSerializer:

    def validate_fields(self, value):
        """ check if selected fields are present in the project and raise error on None
            if no "fields" field is declared in the serializer, no validation
            to write custom validation for serializers with FieldParseSerializer, simply override validate_fields in the project serializer"""
        project_id = self.context['view'].kwargs['project_pk']
        project_obj = Project.objects.get(id=project_id)
        project_fields = set(project_obj.get_elastic_fields(path_list=True))
        if not value or not set(value).issubset(project_fields):
            raise serializers.ValidationError(f'Entered fields not in current project fields: {project_fields}')
        return value


class FieldParseSerializer(FieldValidationSerializer):
    """
    For serializers that need to override to_representation and parse fields
    Serializers overriden with FieldParseSerializer will validate, if field input
    """


    def to_representation(self, instance):
        # self is the parent class obj in this case
        result = super(FieldParseSerializer, self).to_representation(instance)
        model_obj = self.Meta.model.objects.get(id=instance.id)
        fields_to_parse = self.Meta.fields_to_parse
        for field in fields_to_parse:
            if getattr(model_obj, field):
                result[field] = json.loads(getattr(model_obj, field))
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
        help_text="Which indices to use for this procedure.",
        validators=[
            check_for_existence
        ]
    )
