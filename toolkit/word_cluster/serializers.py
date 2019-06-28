from rest_framework import serializers

from toolkit.word_cluster.models import WordCluster
from toolkit.core.task.serializers import TaskSerializer
from toolkit.word_cluster.choices import DEFAULT_NUM_CLUSTERS, DEFAULT_BROWSER_NUM_CLUSTERS, DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER


class WordClusterSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    #embedding = serializers.HyperlinkedRelatedField(view_name='embedding-detail')
    num_clusters = serializers.IntegerField(default=DEFAULT_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_NUM_CLUSTERS}')
    description = serializers.CharField(default='', help_text=f'Default: EMPTY')
    vocab_size = serializers.SerializerMethodField()

    class Meta:
        model = WordCluster
        fields = ('id', 'description', 'embedding', 'vocab_size', 'num_clusters', 'location', 'task')

        read_only_fields = ('author', 'project', 'location', 'task')
    
    def get_vocab_size(self, obj):
        return obj.embedding.vocab_size


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()


class ClusterBrowserSerializer(serializers.Serializer):
    number_of_clusters = serializers.IntegerField(default=DEFAULT_BROWSER_NUM_CLUSTERS, help_text=f'Default: {DEFAULT_BROWSER_NUM_CLUSTERS}')
    max_examples_per_cluster = serializers.IntegerField(default=DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER, help_text=f'Default: {DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER}')
    cluster_order = serializers.ChoiceField(((False, 'ascending'), (True, 'descending')))
