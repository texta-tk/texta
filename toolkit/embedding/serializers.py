from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.embedding.choices import (DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER, DEFAULT_BROWSER_NUM_CLUSTERS, DEFAULT_MIN_FREQ, DEFAULT_NUM_CLUSTERS, DEFAULT_NUM_DIMENSIONS, DEFAULT_OUTPUT_SIZE)
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer


class EmbeddingSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    task = TaskSerializer(read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    num_dimensions = serializers.IntegerField(default=DEFAULT_NUM_DIMENSIONS, help_text=f'Default: {DEFAULT_NUM_DIMENSIONS}')
    min_freq = serializers.IntegerField(default=DEFAULT_MIN_FREQ, help_text=f'Default: {DEFAULT_MIN_FREQ}')
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    url = serializers.SerializerMethodField()


    class Meta:
        model = Embedding
        fields = ('id', 'url', 'author_username', 'description', 'fields', 'query', 'num_dimensions', 'min_freq', 'vocab_size', 'task')
        read_only_fields = ('vocab_size',)
        fields_to_parse = ('fields',)


class EmbeddingPredictSimilarWordsSerializer(serializers.Serializer):
    positives = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words for the model.')
    negatives = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words for the model. Default: EMPTY', required=False, default=[])
    output_size = serializers.IntegerField(default=DEFAULT_OUTPUT_SIZE, help_text=f'Default: {DEFAULT_OUTPUT_SIZE}')


class EmbeddingClusterSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    task = TaskSerializer(read_only=True)
    num_clusters = serializers.IntegerField(default=DEFAULT_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_NUM_CLUSTERS}')
    description = serializers.CharField(default='', help_text=f'Default: EMPTY')
    vocab_size = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()


    class Meta:
        model = EmbeddingCluster
        fields = ('id', 'author_username', 'url', 'description', 'embedding', 'vocab_size', 'num_clusters', 'task')

        read_only_fields = ('task',)


    def get_vocab_size(self, obj):
        return obj.embedding.vocab_size


class EmbeddingClusterBrowserSerializer(serializers.Serializer):
    number_of_clusters = serializers.IntegerField(default=DEFAULT_BROWSER_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_BROWSER_NUM_CLUSTERS}')
    max_examples_per_cluster = serializers.IntegerField(default=DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER, help_text=f'Default: {DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER}')
    cluster_order = serializers.ChoiceField(((False, 'ascending'), (True, 'descending')))
