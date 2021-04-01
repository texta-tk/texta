from rest_framework import serializers

from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.embedding.models import Embedding, Task
from toolkit.embedding import choices
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.choices import get_snowball_choices
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer


class EmbeddingSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    task = TaskSerializer(read_only=True)
    indices = IndexSerializer(many=True, default=[])
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    snowball_language = serializers.ChoiceField(choices=get_snowball_choices(), default=choices.DEFAULT_SNOWBALL_LANGUAGE, help_text=f'Uses Snowball stemmer with specified language to normalize the texts. Default: {choices.DEFAULT_SNOWBALL_LANGUAGE}')
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
    embedding_type = serializers.ChoiceField(choices=choices.EMBEDDING_CHOICES, default=choices.EMBEDDING_CHOICES[0])


    class Meta:
        model = Embedding
        fields = ('id', 'url', 'author_username', 'description', 'indices', 'fields', 'use_phraser', 'embedding_type', 'snowball_language', 'query', 'num_dimensions', 'max_documents', 'min_freq', 'vocab_size', 'task')
        read_only_fields = ('vocab_size',)
        fields_to_parse = ('fields',)


class EmbeddingPredictSimilarWordsSerializer(serializers.Serializer):
    positives_used = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words for the model.')
    negatives_used = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words for the model. Default: EMPTY', required=False, default=[])
    positives_unused = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words in the lexicon, not used in mining. Default: EMPTY', required=False, default=[])
    negatives_unused = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words left out from the lexicon, not used in mining. Default: EMPTY', required=False, default=[])
    
    output_size = serializers.IntegerField(default=choices.DEFAULT_OUTPUT_SIZE,
                                           help_text=f'Default: {choices.DEFAULT_OUTPUT_SIZE}')
