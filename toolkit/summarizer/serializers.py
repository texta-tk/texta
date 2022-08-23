import json
from decimal import *

from django.urls import reverse
from rest_framework import serializers

from toolkit.serializer_constants import CommonModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin
from toolkit.settings import REST_FRAMEWORK
from .models import Summarizer
from .values import DefaultSummarizerValues


class SummarizerSummarizeSerializer(serializers.Serializer):
    text = serializers.CharField(required=True)
    algorithm = serializers.MultipleChoiceField(
        choices=DefaultSummarizerValues.SUPPORTED_ALGORITHMS,
        default=["lexrank"]
    )
    ratio = serializers.DecimalField(max_digits=3, decimal_places=1, default=0.2, min_value=Decimal('0.1'), max_value=99.9, help_text="Min value 0.1, Max value 99.9 anything above 1.0 will be calculated as sentence count.")


class SummarizerIndexSerializer(FieldParseSerializer, serializers.ModelSerializer, CommonModelSerializerMixin, IndicesSerializerMixin):
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    algorithm = serializers.MultipleChoiceField(
        choices=list(DefaultSummarizerValues.SUPPORTED_ALGORITHMS),
        default=["lexrank"]
    )
    fields = serializers.ListField(child=serializers.CharField(), required=True)
    ratio = serializers.DecimalField(max_digits=3, decimal_places=1, default=0.2, min_value=Decimal('0.1'), max_value=99.9, help_text="Min value 0.1, Max value 99.9 anything above 1.0 will be calculated as sentence count.")


    class Meta:
        model = Summarizer
        fields = ("id", "url", "author", "indices", "description", "tasks", "query", "fields", "algorithm", "ratio")
        fields_to_parse = ['fields']


    def get_url(self, obj):
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")
        index = reverse(f"{default_version}:summarizer_index-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def to_representation(self, instance: Summarizer):
        data = super(SummarizerIndexSerializer, self).to_representation(instance)
        data["fields"] = json.loads(instance.fields)
        data["query"] = instance.query
        data["algorithm"] = instance.algorithm
        return data
