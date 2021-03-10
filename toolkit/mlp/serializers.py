import json

from django.urls import reverse
from rest_framework import serializers
from texta_mlp.mlp import SUPPORTED_ANALYZERS

from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.mlp.models import MLPWorker
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


class MLPWorkerSerializer(serializers.ModelSerializer):
    indices = IndexSerializer(many=True, default=[])
    author_username = serializers.CharField(source='author.username', read_only=True, required=False)
    description = serializers.CharField()
    task = TaskSerializer(read_only=True, required=False)
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    fields = serializers.ListField(required=True)
    analyzers = serializers.MultipleChoiceField(
        choices=list(SUPPORTED_ANALYZERS),
        default=["all"]
    )


    class Meta:
        model = MLPWorker
        fields = ("id", "url", "author_username", "indices", "description", "task", "query", "fields", "analyzers")


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
