import json
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.embedding.models import Embedding
from toolkit.rakun_keyword_extractor import choices
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.serializer_constants import FieldParseSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer, ProjectFasttextFilteredPrimaryKeyRelatedField
from toolkit import serializer_constants


class RakunExtractorSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer, IndicesSerializerMixin):
    author_username = serializers.CharField(source="author.profile.get_display_name", read_only=True)
    description = serializers.CharField(required=True, help_text=serializer_constants.DESCRIPTION_HELPTEXT)
    distance_method = serializers.CharField(required=False, default="editdistance", help_text="Default = editdistance")
    distance_threshold = serializers.FloatField(required=False, min_value=0.0, default=2.0, help_text="Distance between tokens that initiates the merge process (if more similar than this, the tokens are merged)")
    num_keywords = serializers.IntegerField(required=False, default=25, help_text="The number of keywords to be detected")
    pair_diff_length = serializers.IntegerField(required=False, default=2, help_text="If the difference in the length of the two tokens is smaller than this parameter, the tokens are considered for merging.")
    stopwords = serializers.ListField(required=False, default=[], help_text="Stop words to add. Default = [].")
    bigram_count_threshold = serializers.IntegerField(required=False, default=2, help_text="Default = 2")
    min_tokens = serializers.IntegerField(required=False, min_value=1, max_value=3, default=1, help_text="The minimum number of tokens that can constitute a keyword")
    max_tokens = serializers.IntegerField(required=False, min_value=1, max_value=2, default=1, help_text="The maximum number of tokens that can constitute a keyword")
    max_similar = serializers.IntegerField(required=False, default=3, help_text="most similar can show up n times")
    max_occurrence = serializers.IntegerField(required=False, default=3, help_text="maximum frequency overall")
    fasttext_embedding = ProjectFasttextFilteredPrimaryKeyRelatedField(queryset=Embedding.objects, many=False, read_only=False, allow_null=True, default=None, help_text=f'FastText Embedding to use. Default = None')
    url = serializers.SerializerMethodField()
    task = TaskSerializer(read_only=True)

    class Meta:
        model = RakunExtractor
        fields = ('id', 'url', 'author_username', 'description', 'distance_method', 'distance_threshold', 'num_keywords', 'pair_diff_length',
                  'stopwords', 'bigram_count_threshold', 'min_tokens', 'max_tokens', 'max_similar', 'max_occurrence',
                  'fasttext_embedding', 'task')
        fields_to_parse = ()

    def validate(self, data):
        if data.get("distance_method", None) == "fasttext":
            if data.get("distance_threshold", None) > 1:
                raise ValidationError("Value 'distance_threshold' should not be greater than one if 'distance_method' is fasttext!")
        return data

    def to_representation(self, instance: RakunExtractor):
        data = super(RakunExtractorSerializer, self).to_representation(instance)
        data["stopwords"] = json.loads(instance.stopwords)
        return data


class RakunExtractorIndexSerializer(FieldParseSerializer, IndicesSerializerMixin):
    description = serializers.CharField(required=True, help_text=f"Text for distinguishing this task from others.")
    fields = serializers.ListField(required=True, child=serializers.CharField(),
                                   help_text=f"Which fields to extract the text from.")
    query = serializers.JSONField(help_text=f"Filter the documents which to scroll and apply to.", default=EMPTY_QUERY)
    bulk_size = serializers.IntegerField(min_value=1, max_value=10000, default=choices.DEFAULT_BULK_SIZE,
                                         help_text=f"How many documents should be sent towards Elasticsearch at once. Default = {choices.DEFAULT_BULK_SIZE}")
    es_timeout = serializers.IntegerField(default=choices.DEFAULT_ES_TIMEOUT,
                                          help_text=f"Elasticsearch scroll timeout in minutes. Default = {choices.DEFAULT_ES_TIMEOUT}.")
    new_fact_name = serializers.CharField(required=False, default="",
                                          help_text=f"Used as fact name when applying the tagger. Defaults to tagger description.")
    new_fact_value = serializers.CharField(required=False, default="",
                                           help_text=f"Used as fact value when applying the tagger. Defaults to tagger match.")
    add_spans = serializers.BooleanField(required=False, default=choices.DEFAULT_ADD_SPANS,
                                         help_text=f"If enabled, spans of detected matches are added to texta facts and corresponding facts can be highlighted in Searcher. Default = {choices.DEFAULT_ADD_SPANS}")


class RakunExtractorRandomDocSerializer(IndicesSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class StopWordSerializer(serializers.Serializer):
    stopwords = serializers.ListField(child=serializers.CharField(required=False), required=True, help_text=f"List of stop words to add.")
    overwrite_existing = serializers.BooleanField(required=False, default=choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS, help_text=f"If enabled, overwrites all existing stop words, otherwise appends to the existing ones. Default: {choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS}.")
