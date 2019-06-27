from rest_framework import serializers

from toolkit.word_cluster.models import WordCluster
from toolkit.core.task.serializers import TaskSerializer


class WordClusterSerializer(serializers.ModelSerializer):
    task = TaskSerializer(read_only=True)
    num_clusters = serializers.IntegerField(default=500)

    class Meta:
        model = WordCluster
        fields = ('id', 'description', 'embedding', 'num_clusters', 'task')

        read_only_fields = ('author', 'project', 'location', 'task')