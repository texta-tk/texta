import json
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from toolkit.core.task.serializers import TaskSerializer
from toolkit.embedding.models import Embedding
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.rakun_keyword_extractor import choices
from toolkit.rakun_keyword_extractor.models import RakunExtractor
from toolkit.serializer_constants import FieldParseSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer, ProjectFasttextFilteredPrimaryKeyRelatedField
from toolkit import serializer_constants


class RakunExtractorSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer, IndicesSerializerMixin):
    author_username = serializers.CharField(source="author.profile.get_display_name", read_only=True)
    description = serializers.CharField(required=True, help_text=serializer_constants.DESCRIPTION_HELPTEXT)
    fields = serializers.ListField(required=True, child=serializers.CharField(),
                                   help_text=serializer_constants.FIELDS_HELPTEXT)
    query = serializers.JSONField(help_text=serializer_constants.QUERY_HELPTEXT, required=False, default=json.dumps(EMPTY_QUERY))
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
        fields = ('id', 'url', 'author_username', 'description', 'indices', 'fields', 'query', 'distance_method', 'distance_threshold', 'num_keywords', 'pair_diff_length',
                  'stopwords', 'bigram_count_threshold', 'min_tokens', 'max_tokens', 'max_similar', 'max_occurrence',
                  'fasttext_embedding', 'task')
        fields_to_parse = ('fields',)

    def validate(self, data):
        if data.get("distance_method", None) == "fasttext":
            if data.get("distance_threshold", None) > 1:
                raise ValidationError("Value 'distance_threshold' should not be greater than one if 'distance_method' is fasttext!")
        return data

    def to_representation(self, instance: RakunExtractor):
        data = super(RakunExtractorSerializer, self).to_representation(instance)
        data["fields"] = json.loads(instance.fields)
        data["query"] = json.loads(instance.query)
        data["stopwords"] = json.loads(instance.stopwords)
        return data


class RakunExtractorRandomDocSerializer(IndicesSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class StopWordSerializer(serializers.Serializer):
    stopwords = serializers.ListField(child=serializers.CharField(required=False), required=True, help_text=f"List of stop words to add.")
    overwrite_existing = serializers.BooleanField(required=False, default=choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS, help_text=f"If enabled, overwrites all existing stop words, otherwise appends to the existing ones. Default: {choices.DEFAULT_OVERWRITE_EXISTING_STOPWORDS}.")
