from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.embedding.models import Embedding
from toolkit.rakun_keyword_extractor import choices
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.serializer_constants import CommonModelSerializerMixin, FavoriteModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin, ProjectFasttextFilteredPrimaryKeyRelatedField, ProjectResourceUrlSerializer


class RakunExtractorSerializer(FieldParseSerializer, serializers.ModelSerializer, CommonModelSerializerMixin, ProjectResourceUrlSerializer, IndicesSerializerMixin, FavoriteModelSerializerMixin, ):
    distance_method = serializers.ChoiceField(choices=choices.DEFAULT_DISTANCE_METHOD_CHOICES, default=choices.DEFAULT_DISTANCE_METHOD,
                                              help_text="Method for merging similar tokens.")
    distance_threshold = serializers.FloatField(required=False, min_value=0.0, default=2.0, help_text="Distance between tokens that initiates the merge process (if more similar than this, the tokens are merged).")
    num_keywords = serializers.IntegerField(required=False, default=25, help_text="The number of keywords to be detected")
    pair_diff_length = serializers.IntegerField(required=False, default=2, help_text="If the difference in the length of the two tokens is smaller than this parameter, the tokens are considered for merging.")
    stopwords = serializers.ListField(child=serializers.CharField(required=False), required=False, default=[], help_text="Words to ignore as possible keywords.")
    bigram_count_threshold = serializers.IntegerField(required=False, default=2, help_text="Minimum edge weight for constituting a bigram.")
    min_tokens = serializers.IntegerField(required=False, min_value=1, max_value=3, default=1, help_text="The minimum number of tokens that can constitute a keyword.")
    max_tokens = serializers.IntegerField(required=False, min_value=1, max_value=3, default=1, help_text="The maximum number of tokens that can constitute a keyword.")
    max_similar = serializers.IntegerField(required=False, default=3, help_text="How many similar keywords are permitted. For example, 'british vote' and 'british parliament' would be considered similar (overlap of at least one token).")
    max_occurrence = serializers.IntegerField(required=False, default=3, help_text="How many of the most common keywords are to be considered during max_similar prunning step.")
    fasttext_embedding = ProjectFasttextFilteredPrimaryKeyRelatedField(queryset=Embedding.objects, many=False, read_only=False, allow_null=True, default=None, help_text=f'FastText embedding to use.')
    url = serializers.SerializerMethodField()


    class Meta:
        model = RakunExtractor
        fields = ('id', 'url', 'author', 'description', 'distance_method', 'distance_threshold', 'num_keywords', 'pair_diff_length',
                  'stopwords', 'bigram_count_threshold', 'min_tokens', 'is_favorited', 'max_tokens', 'max_similar', 'max_occurrence',
                  'fasttext_embedding', 'tasks')
        fields_to_parse = ()


    def validate(self, data):
        if data.get("distance_method", None) == "fasttext":
            if data.get("distance_threshold", None) > 1:
                raise ValidationError("Value 'distance_threshold' should not be greater than one if 'distance_method' is fasttext!")
        return data


    def to_representation(self, instance: RakunExtractor):
        data = super(RakunExtractorSerializer, self).to_representation(instance)
        data.pop("stopwords")
        return data


class RakunExtractorIndexSerializer(FieldParseSerializer, IndicesSerializerMixin):
    description = serializers.CharField(required=True, help_text=f"Text for distinguishing this task from others.")
    fields = serializers.ListField(required=True, child=serializers.CharField(),
                                   help_text=f"Which fields to extract the text from.")
    query = serializers.JSONField(help_text=f"Filter the documents which to scroll and apply to.", default=EMPTY_QUERY)
    bulk_size = serializers.IntegerField(min_value=1, max_value=10000, default=choices.DEFAULT_BULK_SIZE,
                                         help_text=f"How many documents should be sent towards Elasticsearch at once.")
    es_timeout = serializers.IntegerField(default=choices.DEFAULT_ES_TIMEOUT,
                                          help_text=f"Elasticsearch scroll timeout in minutes.")
    new_fact_name = serializers.CharField(required=False, default="",
                                          help_text=f"Used as fact name when applying the tagger. Defaults to Rakun description.")
    add_spans = serializers.BooleanField(required=False, default=choices.DEFAULT_ADD_SPANS,
                                         help_text=f"If enabled, spans of detected matches are added to texta facts and corresponding facts can be highlighted in Searcher.")


class RakunExtractorTextSerializer(serializers.Serializer):
    text = serializers.CharField(required=True, help_text="Text to process with Rakun")
    add_spans = serializers.BooleanField(required=False, default=choices.DEFAULT_ADD_SPANS,
                                         help_text=f"If enabled, spans of detected matches are added to texta facts and corresponding facts can be highlighted in Searcher.")


class RakunExtractorRandomDocSerializer(IndicesSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)
    add_spans = serializers.BooleanField(required=False, default=choices.DEFAULT_ADD_SPANS,
                                         help_text=f"If enabled, spans of detected matches are added to texta facts and corresponding facts can be highlighted in Searcher.")


class StopWordSerializer(serializers.Serializer):
    stopwords = serializers.ListField(child=serializers.CharField(required=False), required=True, help_text=f"Words to ignore as possible keywords.")
    overwrite_existing = serializers.BooleanField(required=False, default=choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS, help_text=f"If enabled, overwrites all existing stop words, otherwise appends to the existing ones.")
