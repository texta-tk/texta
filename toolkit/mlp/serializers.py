import json

from rest_framework import serializers

from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.mlp.choices import MLP_ANALYZER_CHOICES
from toolkit.mlp.models import MLPProcessor


class MLPElasticSerializer(serializers.ModelSerializer):
    query = serializers.JSONField(default=json.dumps(EMPTY_QUERY), required=False)
    analyzers = serializers.MultipleChoiceField(choices=MLP_ANALYZER_CHOICES, required=False)
    fields = serializers.ListField(child=serializers.CharField())
    indices = serializers.ListField(child=serializers.CharField(), required=True)


    class Meta:
        model = MLPProcessor
        fields = ('id', 'description', 'indices', 'fields', 'query', 'analyzers')
