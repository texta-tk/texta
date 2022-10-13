import json

from django.urls import reverse
from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import BULK_SIZE_HELPTEXT, CommonModelSerializerMixin, DESCRIPTION_HELPTEXT, ES_TIMEOUT_HELPTEXT, FIELDS_HELPTEXT, FieldsValidationSerializerMixin, IndicesSerializerMixin, QUERY_HELPTEXT
from toolkit.settings import REST_FRAMEWORK
from .models import SearchFieldsTagger, SearchQueryTagger
from ...core.user_profile.serializers import UserSerializer


class SearchQueryTaggerSerializer(serializers.ModelSerializer, CommonModelSerializerMixin, FieldsValidationSerializerMixin, IndicesSerializerMixin):
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text=QUERY_HELPTEXT, default=EMPTY_QUERY)
    fields = serializers.ListField(child=serializers.CharField(), help_text=FIELDS_HELPTEXT, required=True)
    fact_name = serializers.CharField(required=True, help_text="What name should the newly created facts have.")
    fact_value = serializers.CharField(required=True, help_text="What value should the newly created facts have.")
    bulk_size = serializers.IntegerField(min_value=1, default=100, help_text=BULK_SIZE_HELPTEXT)
    es_timeout = serializers.IntegerField(min_value=1, default=10, help_text=ES_TIMEOUT_HELPTEXT)


    class Meta:
        model = SearchQueryTagger
        fields = ("id", "url", "author", "indices", "description", "tasks", "query", "fields", "fact_name", "fact_value", "bulk_size", "es_timeout")


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


class SearchFieldsTaggerSerializer(serializers.ModelSerializer, CommonModelSerializerMixin, FieldsValidationSerializerMixin, IndicesSerializerMixin):
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text=QUERY_HELPTEXT, default=EMPTY_QUERY)
    fields = serializers.ListField(child=serializers.CharField(), required=True, help_text=FIELDS_HELPTEXT)
    fact_name = serializers.CharField(help_text="What name should the newly created facts have.")

    use_breakup = serializers.BooleanField(default=True, help_text="Whether to split the text into multiple facts by the breakup character.")
    breakup_character = serializers.CharField(default="\n", help_text="Which text/symbol to use to split the text into separate facts.", trim_whitespace=False)

    bulk_size = serializers.IntegerField(min_value=1, default=100, help_text=BULK_SIZE_HELPTEXT)
    es_timeout = serializers.IntegerField(min_value=1, default=10, help_text=ES_TIMEOUT_HELPTEXT)


    class Meta:
        model = SearchFieldsTagger
        fields = ("id", "url", "author", "indices", "description", "use_breakup", "breakup_character", "tasks", "query", "fields", "fact_name", "bulk_size", "es_timeout")


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
