from rest_framework import serializers
import json
import re

from toolkit.embedding.models import Embedding, Task, EmbeddingCluster
from toolkit.embedding.choices import (get_field_choices, DEFAULT_NUM_DIMENSIONS, DEFAULT_MAX_VOCAB, DEFAULT_MIN_FREQ, DEFAULT_OUTPUT_SIZE,
                                       DEFAULT_NUM_CLUSTERS, DEFAULT_BROWSER_NUM_CLUSTERS, DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER)
from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import ProjectResourceUrlSerializer

class EmbeddingSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    task = TaskSerializer(read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    num_dimensions = serializers.IntegerField(default=DEFAULT_NUM_DIMENSIONS,
                                    help_text=f'Default: {DEFAULT_NUM_DIMENSIONS}')
    min_freq = serializers.IntegerField(default=DEFAULT_MIN_FREQ,
                                    help_text=f'Default: {DEFAULT_MIN_FREQ}')
    fields_parsed = serializers.SerializerMethodField()
    query = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = Embedding
        fields = ('id', 'url', 'description', 'fields', 'query', 'num_dimensions', 'min_freq', 'vocab_size', 'task', 'fields_parsed')
        read_only_fields = ('vocab_size',)


    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None

    def get_query(self, obj):
        if obj.query:
            return json.loads(obj.query)
        return None


class EmbeddingPrecictionSerializer(serializers.Serializer):
    positives = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words for the model.')
    negatives = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words for the model. Default: EMPTY', required=False, default=[])
    output_size = serializers.IntegerField(default=DEFAULT_OUTPUT_SIZE,
                                    help_text=f'Default: {DEFAULT_OUTPUT_SIZE}')


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()


class EmbeddingClusterSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    task = TaskSerializer(read_only=True)
    num_clusters = serializers.IntegerField(default=DEFAULT_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_NUM_CLUSTERS}')
    description = serializers.CharField(default='', help_text=f'Default: EMPTY')
    vocab_size = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = EmbeddingCluster
        fields = ('id', 'url', 'description', 'embedding', 'vocab_size', 'num_clusters', 'location', 'task')

        read_only_fields = ('task',)

    def get_vocab_size(self, obj):
        return obj.embedding.vocab_size

    def get_location(self, obj):
        return json.loads(obj.location)

class ClusterBrowserSerializer(serializers.Serializer):
    number_of_clusters = serializers.IntegerField(default=DEFAULT_BROWSER_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_BROWSER_NUM_CLUSTERS}')
    max_examples_per_cluster = serializers.IntegerField(default=DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER, help_text=f'Default: {DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER}')
    cluster_order = serializers.ChoiceField(((False, 'ascending'), (True, 'descending')))