from rest_framework import serializers

from toolkit.elastic.serializers import IndexSerializer
from toolkit.embedding.models import Embedding, Task
from toolkit.embedding import choices
from toolkit.core.task.serializers import TaskSerializer
from toolkit.embedding.choices import (
    DEFAULT_MIN_FREQ,
    DEFAULT_NUM_DIMENSIONS,
    DEFAULT_OUTPUT_SIZE
)
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from toolkit.settings import FASTTEXT_EMBEDDING, W2V_EMBEDDING


class EmbeddingSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    task = TaskSerializer(read_only=True)
    indices = IndexSerializer(many=True, default=[])
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    max_documents = serializers.IntegerField(default=choices.DEFAULT_MAX_DOCUMENTS)
    num_dimensions = serializers.IntegerField(
        default=choices.DEFAULT_NUM_DIMENSIONS,
        help_text=f'Default: {choices.DEFAULT_NUM_DIMENSIONS}'
    )
    min_freq = serializers.IntegerField(
        default=choices.DEFAULT_MIN_FREQ,
        help_text=f'Default: {choices.DEFAULT_MIN_FREQ}'
    )
    use_phraser = serializers.BooleanField(
        default=True,
        help_text='Phrase input texts.'
    )
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    url = serializers.SerializerMethodField()
    embedding_type = serializers.ChoiceField(choices = [FASTTEXT_EMBEDDING, W2V_EMBEDDING], default=W2V_EMBEDDING)


    class Meta:
        model = Embedding
        fields = ('id', 'url', 'author_username', 'description', 'indices', 'fields', 'use_phraser', 'embedding_type', 'query', 'num_dimensions', 'max_documents', 'min_freq', 'vocab_size', 'task')
        read_only_fields = ('vocab_size',)
        fields_to_parse = ('fields',)


class EmbeddingPredictSimilarWordsSerializer(serializers.Serializer):
    positives_used = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words for the model.')
    negatives_used = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words for the model. Default: EMPTY', required=False, default=[])
    positives_unused = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words in the lexicon, not used in mining. Default: EMPTY', required=False, default=[])
    negatives_unused = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words left out from the lexicon, not used in mining. Default: EMPTY', required=False, default=[])
    
    output_size = serializers.IntegerField(default=choices.DEFAULT_OUTPUT_SIZE,
                                           help_text=f'Default: {choices.DEFAULT_OUTPUT_SIZE}')
