import json
from typing import Union

from django.urls import reverse
from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY
from texta_mlp.mlp import SUPPORTED_ANALYZERS

from toolkit.core.project.models import Project
from toolkit.mlp.models import ApplyLangWorker, MLPWorker
from toolkit.serializer_constants import CommonModelSerializerMixin, FieldsValidationSerializerMixin, IndicesSerializerMixin
from toolkit.settings import REST_FRAMEWORK


class MLPListSerializer(serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(), required=True)
    analyzers = serializers.MultipleChoiceField(
        choices=SUPPORTED_ANALYZERS,
        default=["all"]
    )


class MLPDocsSerializer(serializers.Serializer):
    docs = serializers.ListField(child=serializers.DictField(), required=True)
    fields_to_parse = serializers.ListField(child=serializers.CharField(), required=True)
    analyzers = serializers.MultipleChoiceField(
        choices=SUPPORTED_ANALYZERS,
        default=["all"]
    )


class MLPWorkerSerializer(serializers.ModelSerializer, IndicesSerializerMixin, CommonModelSerializerMixin, FieldsValidationSerializerMixin):
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False, default=json.dumps(EMPTY_QUERY))
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False, help_text="Which fields to apply the MLP on.")
    analyzers = serializers.MultipleChoiceField(
        choices=list(SUPPORTED_ANALYZERS),
        default=["all"]
    )
    es_scroll_size = serializers.IntegerField(help_text="Scroll size for Elasticsearch (Default: 100)", default=100, required=False)
    es_timeout = serializers.IntegerField(help_text="Scroll timeout in minutes for Elasticsearch (Default: 60)", default=60, required=False)


    class Meta:
        model = MLPWorker
        fields = ("id", "url", "author", "indices", "description", "tasks", "query", "fields", "analyzers", "es_scroll_size", "es_timeout")


    def get_url(self, obj):
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")
        index = reverse(f"{default_version}:mlp_index-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def to_representation(self, instance: MLPWorker):
        data = super(MLPWorkerSerializer, self).to_representation(instance)
        data["fields"] = json.loads(instance.fields)
        data["query"] = json.loads(instance.query)
        data["analyzers"] = json.loads(instance.analyzers)
        return data


class LangDetectSerializer(serializers.Serializer):
    text = serializers.CharField()


class ApplyLangOnIndicesSerializer(serializers.ModelSerializer, CommonModelSerializerMixin, IndicesSerializerMixin, FieldsValidationSerializerMixin):
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False, default=json.dumps(EMPTY_QUERY))
    field = serializers.CharField(required=True, allow_blank=False)


    def validate_field(self, value: str):
        """
        Check if selected fields are present in the project and raise error on None
        if no "fields" field is declared in the serializer, no validation
        to write custom validation for serializers with FieldParseSerializer, simply override validate_fields in the project serializer
        """
        project_id = self.context['view'].kwargs['project_pk']
        project_obj = Project.objects.get(id=project_id)
        project_fields = set(project_obj.get_elastic_fields(path_list=True))
        if not value or not set([value]).issubset(project_fields):
            raise serializers.ValidationError(f'Entered fields not in current project fields: {project_fields}')
        return value


    def validate_query(self, query: Union[str, dict]):
        """
        Check if the query is formatted correctly and store it as JSON string,
        if it is passed as a JSON dict.
        """
        if not isinstance(query, dict):
            try:
                query = json.loads(query)
            except:
                raise serializers.ValidationError(f"Incorrect query: '{query}'. Query should be formatted as a JSON dict or a JSON string.")
            # If loaded query is not JSON dict, raise ValidatioNError
            if not isinstance(query, dict):
                raise serializers.ValidationError(f"Incorrect query: '{query}'. Query should contain a JSON dict.")

        # Ensure that the query is stored as a JSON string
        query = json.dumps(query)
        return query


    class Meta:
        model = ApplyLangWorker
        fields = ("id", "url", "author", "indices", "description", "tasks", "query", "field")


    def get_url(self, obj):
        default_version = "v2"
        index = reverse(f"{default_version}:lang_index-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def to_representation(self, instance: ApplyLangWorker):
        data = super(ApplyLangOnIndicesSerializer, self).to_representation(instance)
        data["query"] = json.loads(instance.query)
        return data
