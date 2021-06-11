import json

from django.urls import reverse
from rest_framework import serializers
from texta_mlp.mlp import SUPPORTED_ANALYZERS

from toolkit.core.project.models import Project
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.mlp.models import ApplyLangWorker, MLPWorker
from toolkit.serializer_constants import FieldValidationSerializer
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


class MLPWorkerSerializer(serializers.ModelSerializer, FieldValidationSerializer):
    indices = IndexSerializer(many=True, default=[])
    author_username = serializers.CharField(source='author.username', read_only=True, required=False)
    description = serializers.CharField()
    task = TaskSerializer(read_only=True, required=False)
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False, help_text="Which fields to apply the MLP on.")
    analyzers = serializers.MultipleChoiceField(
        choices=list(SUPPORTED_ANALYZERS),
        default=["all"]
    )
    es_scroll_size = serializers.IntegerField(help_text="Scroll size for Elasticsearch (Default: 100)", required=False)
    es_timeout = serializers.IntegerField(help_text="Scroll timeout in minutes for Elasticsearch (Default: 30)", required=False)


    class Meta:
        model = MLPWorker
        fields = ("id", "url", "author_username", "indices", "description", "task", "query", "fields", "analyzers", "es_scroll_size", "es_timeout")


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


class ApplyLangOnIndicesSerializer(serializers.ModelSerializer, FieldValidationSerializer):
    description = serializers.CharField()
    indices = IndexSerializer(many=True, default=[])
    author_username = serializers.CharField(source='author.username', read_only=True, required=False)
    task = TaskSerializer(read_only=True, required=False)
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
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


    class Meta:
        model = ApplyLangWorker
        fields = ("id", "url", "author_username", "indices", "description", "task", "query", "field")


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
