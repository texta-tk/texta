from rest_framework import serializers

from toolkit.elastic.choices import DEFAULT_SNOWBALL_LANGUAGE, get_snowball_choices
from toolkit.embedding import choices
from toolkit.embedding.models import Embedding
from toolkit.serializer_constants import CommonModelSerializerMixin, FavoriteModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer


class EmbeddingSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, CommonModelSerializerMixin, ProjectResourceUrlSerializer, FavoriteModelSerializerMixin, IndicesSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    snowball_language = serializers.ChoiceField(choices=get_snowball_choices(), default=DEFAULT_SNOWBALL_LANGUAGE, help_text=f'Uses Snowball stemmer with specified language to normalize the texts. Default: {DEFAULT_SNOWBALL_LANGUAGE}')
    max_documents = serializers.IntegerField(default=choices.DEFAULT_MAX_DOCUMENTS)
    stop_words = serializers.ListField(child=serializers.CharField(), allow_empty=False, default=[])
    num_dimensions = serializers.IntegerField(
        default=choices.DEFAULT_NUM_DIMENSIONS,
        help_text=f'Default: {choices.DEFAULT_NUM_DIMENSIONS}'
    )
    min_freq = serializers.IntegerField(
        default=choices.DEFAULT_MIN_FREQ,
        help_text=f'Default: {choices.DEFAULT_MIN_FREQ}'
    )
    window_size = serializers.IntegerField(min_value=1, default=5, help_text="Maximum distance between the current and predicted word within a sentence.")
    num_epochs = serializers.IntegerField(min_value=1, default=5, help_text="Number of iterations (epochs) over the corpus.")
    use_phraser = serializers.BooleanField(
        default=True,
        help_text='Phrase input texts.'
    )
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    url = serializers.SerializerMethodField()
    embedding_type = serializers.ChoiceField(choices=choices.EMBEDDING_CHOICES, default=choices.EMBEDDING_CHOICES[0][0])


    class Meta:
        model = Embedding
        fields = ('id', 'url', 'author', 'description', 'indices', 'fields', 'use_phraser', 'embedding_type', 'is_favorited', 'snowball_language', 'query', 'stop_words', 'num_dimensions', 'max_documents', 'min_freq', 'window_size', 'num_epochs', 'vocab_size', 'tasks')
        read_only_fields = ('vocab_size',)
        fields_to_parse = ('fields', 'stop_words')


class EmbeddingPredictSimilarWordsSerializer(serializers.Serializer):
    positives_used = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words for the model.')
    negatives_used = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words for the model. Default: EMPTY', required=False, default=[])
    positives_unused = serializers.ListField(child=serializers.CharField(), help_text=f'Positive words in the lexicon, not used in mining. Default: EMPTY', required=False, default=[])
    negatives_unused = serializers.ListField(child=serializers.CharField(), help_text=f'Negative words left out from the lexicon, not used in mining. Default: EMPTY', required=False, default=[])

    output_size = serializers.IntegerField(default=choices.DEFAULT_OUTPUT_SIZE,
                                           help_text=f'Default: {choices.DEFAULT_OUTPUT_SIZE}')
