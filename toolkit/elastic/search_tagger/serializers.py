import json
from .models import SearchQueryTagger, SearchFieldsTagger
from rest_framework import serializers
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.serializer_constants import FieldValidationSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.settings import REST_FRAMEWORK
from django.urls import reverse


class SearchQueryTaggerSerializer(serializers.ModelSerializer, FieldValidationSerializer):
    indices = IndexSerializer(many=True, default=[])
    author_username = serializers.CharField(source='author.username', read_only=True, required=False)
    description = serializers.CharField()
    task = TaskSerializer(read_only=True, required=False)
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', default=EMPTY_QUERY)
    fields = serializers.ListField(child=serializers.CharField(), required=True)
    fact_name = serializers.CharField(required=True)
    fact_value = serializers.CharField(required=True)
    bulk_size = serializers.IntegerField(min_value=1, default=100)
    es_timeout = serializers.IntegerField(min_value=1, default=10)

    class Meta:
        model = SearchQueryTagger
        fields = ("id", "url", "author_username", "indices", "description", "task", "query", "fields", "fact_name", "fact_value", "bulk_size", "es_timeout")

    def get_url(self, obj):
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")
        index = reverse(f"{default_version}:search_query_tagger-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None

    def to_representation(self, instance: SearchQueryTagger):
        data = super(SearchQueryTaggerSerializer, self).to_representation(instance)
        data["fields"] = json.loads(instance.fields)
        data["query"] = json.loads(instance.query)
        return data


class SearchFieldsTaggerSerializer(serializers.ModelSerializer, FieldValidationSerializer):
    indices = IndexSerializer(many=True, default=[])
    author_username = serializers.CharField(source='author.username', read_only=True, required=False)
    description = serializers.CharField()
    task = TaskSerializer(read_only=True, required=False)
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', default=EMPTY_QUERY)
    fields = serializers.ListField(child=serializers.CharField(), required=True)
    fact_name = serializers.CharField()
    bulk_size = serializers.IntegerField(min_value=1, default=100)
    es_timeout = serializers.IntegerField(min_value=1, default=10)

    class Meta:
        model = SearchFieldsTagger
        fields = ("id", "url", "author_username", "indices", "description", "task", "query", "fields", "fact_name", "bulk_size", "es_timeout")

    def get_url(self, obj):
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")
        index = reverse(f"{default_version}:search_fields_tagger-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None

    def to_representation(self, instance: SearchFieldsTagger):
        data = super(SearchFieldsTaggerSerializer, self).to_representation(instance)
        data["fields"] = json.loads(instance.fields)
        data["query"] = json.loads(instance.query)
        return data
