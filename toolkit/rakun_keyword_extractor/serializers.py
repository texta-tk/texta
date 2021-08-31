from rest_framework import serializers
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.serializer_constants import IndicesSerializerMixin, ProjectResourceUrlSerializer

class RakunExtractorSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer, IndicesSerializerMixin):
    author_username = serializers.CharField(source="author.profile.get_display_name", read_only=True)
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    distance_threshold = serializers.FloatField(required=False, min_value=1.0, default=2.0, help_text="Distance between tokens that initiates the merge process (if more similar than this, the tokens are merged)")
    num_keywords = serializers.IntegerField(required=False, default=25, help_text="The number of keywords to be detected")
    pair_diff_length = serializers.IntegerField(required=False, default=2, help_text="If the difference in the length of the two tokens is smaller than this parameter, the tokens are considered for merging.")
    stopwords = serializers.CharField(required=False, default=[], help_text="")
    bigram_count_threshold = serializers.IntegerField(required=False, default=2)
    min_tokens = serializers.IntegerField(required=False, min_value=1, max_value=3, default=1, help_text="The minimum number of tokens that can constitute a keyword")
    max_tokens = serializers.IntegerField(required=False, min_value=1, max_value=2, default=1, help_text="The maximum number of tokens that can constitute a keyword")
    max_similar = serializers.IntegerField(required=False, default=3, help_text="most similar can show up n times")
    max_occurrence = serializers.IntegerField(required=False, default=3, help_text="maximum frequency overall")
    fasttext_embedding = serializers.CharField(required=False, default=None)

    class Meta:
        model = RakunExtractor
        fields = ('id', 'author_username', 'description', 'distance_threshold', 'num_keywords', 'pair_diff_length',
                  'stopwords', 'bigram_count_threshold', 'min_tokens', 'max_tokens', 'max_similar', 'max_occurrence',
                  'fasttext_embedding')
        read_only_fields = ()
        fields_to_parse = ('fields',)
