from rest_framework import serializers

from toolkit.embedding.models import Embedding, Task, EmbeddingCluster
from toolkit.embedding.choices import (get_field_choices, DEFAULT_NUM_DIMENSIONS, DEFAULT_MAX_VOCAB, DEFAULT_MIN_FREQ, DEFAULT_OUTPUT_SIZE,
                                       DEFAULT_NUM_CLUSTERS, DEFAULT_BROWSER_NUM_CLUSTERS, DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER)
from toolkit.core.task.serializers import TaskSerializer



class EmbeddingSerializer(serializers.HyperlinkedModelSerializer):
    task = TaskSerializer(read_only=True)
    fields = serializers.MultipleChoiceField(choices=get_field_choices())
    num_dimensions = serializers.IntegerField(default=DEFAULT_NUM_DIMENSIONS,
                                    help_text=f'Default: {DEFAULT_NUM_DIMENSIONS}')
    #max_vocab = serializers.IntegerField(default=DEFAULT_MAX_VOCAB,
    #                                help_text=f'Default: {DEFAULT_MAX_VOCAB}')
    min_freq = serializers.IntegerField(default=DEFAULT_MIN_FREQ,
                                    help_text=f'Default: {DEFAULT_MIN_FREQ}')
    
    class Meta:
        model = Embedding
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'num_dimensions', 'min_freq', 'vocab_size', 'location', 'task')
        read_only_fields = ('vocab_size', 'location', 'author', 'project')


class EmbeddingPrecictionSerializer(serializers.Serializer):
    text = serializers.CharField()
    output_size = serializers.IntegerField(default=DEFAULT_OUTPUT_SIZE,
                                    help_text=f'Default: {DEFAULT_OUTPUT_SIZE}')

class PhrasePrecictionSerializer(serializers.Serializer):
    text = serializers.CharField()


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()


class EmbeddingClusterSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    num_clusters = serializers.IntegerField(default=DEFAULT_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_NUM_CLUSTERS}')
    description = serializers.CharField(default='', help_text=f'Default: EMPTY')
    vocab_size = serializers.SerializerMethodField()

    class Meta:
        model = EmbeddingCluster
        fields = ('id', 'description', 'embedding', 'vocab_size', 'num_clusters', 'location', 'task')

        read_only_fields = ('author', 'project', 'location', 'task')
    
    def get_vocab_size(self, obj):
        return obj.embedding.vocab_size


class ClusterBrowserSerializer(serializers.Serializer):
    number_of_clusters = serializers.IntegerField(default=DEFAULT_BROWSER_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_BROWSER_NUM_CLUSTERS}')
    max_examples_per_cluster = serializers.IntegerField(default=DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER, help_text=f'Default: {DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER}')
    cluster_order = serializers.ChoiceField(((False, 'ascending'), (True, 'descending')))
