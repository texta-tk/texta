from rest_framework import serializers

from toolkit.embedding.models import Embedding, Task
from toolkit.embedding.choices import get_field_choices, EMBEDDING_CHOICES, DEFAULT_NUM_DIMENSIONS, DEFAULT_MAX_VOCAB, DEFAULT_MIN_FREQ, DEFAULT_OUTPUT_SIZE
from toolkit.core.task.serializers import TaskSerializer


class EmbeddingSerializer(serializers.HyperlinkedModelSerializer):
    task = TaskSerializer(read_only=True)
    fields = serializers.MultipleChoiceField(choices=get_field_choices())
    num_dimensions = serializers.IntegerField(default=DEFAULT_NUM_DIMENSIONS,
                                    help_text=f'Default: {DEFAULT_NUM_DIMENSIONS}')
    max_vocab = serializers.IntegerField(default=DEFAULT_MAX_VOCAB,
                                    help_text=f'Default: {DEFAULT_MAX_VOCAB}')
    min_freq = serializers.IntegerField(default=DEFAULT_MIN_FREQ,
                                    help_text=f'Default: {DEFAULT_MIN_FREQ}')
    
    class Meta:
        model = Embedding
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'num_dimensions', 'max_vocab', 'min_freq', 'vocab_size', 'location', 'task')
        read_only_fields = ('vocab_size', 'location', 'author', 'project')


class EmbeddingPrecictionSerializer(serializers.Serializer):
    text = serializers.CharField()
    output_size = serializers.ChoiceField(default=DEFAULT_OUTPUT_SIZE,
                                    help_text=f'Default: {DEFAULT_OUTPUT_SIZE}')

class PhrasePrecictionSerializer(serializers.Serializer):
    text = serializers.CharField()
