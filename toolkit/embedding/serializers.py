from rest_framework import serializers

from toolkit.embedding.models import Embedding, Task
from toolkit.embedding.choices import EMBEDDING_CHOICES, get_field_choices
from toolkit.core.serializers import TaskSerializer


class EmbeddingSerializer(serializers.HyperlinkedModelSerializer):
    vocab_size = serializers.IntegerField(read_only=True)
    location = serializers.CharField(read_only=True)
    task = TaskSerializer(read_only=True)
    fields = serializers.MultipleChoiceField(choices=get_field_choices())
    num_dimensions = serializers.ChoiceField(choices=EMBEDDING_CHOICES['num_dimensions'])
    max_vocab = serializers.ChoiceField(choices=EMBEDDING_CHOICES['max_vocab'])
    min_freq = serializers.ChoiceField(choices=EMBEDDING_CHOICES['min_freq'])
    vocab_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = Embedding
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'num_dimensions', 'max_vocab', 'min_freq', 'vocab_size', 'location', 'task')
