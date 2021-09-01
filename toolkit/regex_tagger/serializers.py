from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.regex_tagger import choices
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup
from toolkit.regex_tagger.validators import validate_patterns
from toolkit.serializer_constants import FieldParseSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer


class RegexTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()
    author = UserSerializer(read_only=True)
    lexicon = serializers.ListField(child=serializers.CharField(required=True), validators=[validate_patterns], help_text="Words/phrases/regex patterns to match.")
    counter_lexicon = serializers.ListField(child=serializers.CharField(required=False), default=[], validators=[validate_patterns], help_text="Words/phrases/regex patterns to nullify lexicon matches. Default = [].")

    operator = serializers.ChoiceField(default=choices.DEFAULT_OPERATOR, choices=choices.OPERATOR_CHOICES, required=False, help_text=f"Logical operation between lexicon entries. Choices =  {choices.OPERATOR_CHOICES}. Default = {choices.DEFAULT_OPERATOR}.")
    match_type = serializers.ChoiceField(default=choices.DEFAULT_MATCH_TYPE, choices=choices.MATCH_TYPE_CHOICES, required=False, help_text=f"How to match lexicon entries to text. Choices = {choices.SUPPORTED_MATCH_TYPES}. Default= {choices.DEFAULT_MATCH_TYPE}.")
    required_words = serializers.FloatField(default=choices.DEFAULT_REQUIRED_WORDS, required=False, help_text=f"Required ratio of lexicon entries matched in text for returning a positive result. NB! Only takes effect if operator=='and'. Default = {choices.DEFAULT_REQUIRED_WORDS}.")
    phrase_slop = serializers.IntegerField(default=choices.DEFAULT_PHRASE_SLOP, required=False, help_text=f"Number of non-lexicon words allowed between the words of one lexicon entry. Default = {choices.DEFAULT_PHRASE_SLOP}.")
    counter_slop = serializers.IntegerField(default=choices.DEFAULT_COUNTER_SLOP, required=False, help_text=f"Number of words allowed between lexicon entries and counter lexicon entries for the latter to have effect. Default = {choices.DEFAULT_COUNTER_SLOP}")
    n_allowed_edits = serializers.IntegerField(default=choices.DEFAULT_N_ALLOWED_EDITS, required=False, help_text=f"Number of allowed character changes between lexicon entries and candidate matches in text. Default = {choices.DEFAULT_N_ALLOWED_EDITS}.")
    return_fuzzy_match = serializers.BooleanField(default=choices.DEFAULT_RETURN_FUZZY_MATCH, required=False, help_text=f"Return fuzzy match (opposed to exact lexicon entry)? Default = {choices.DEFAULT_RETURN_FUZZY_MATCH}.")
    ignore_case = serializers.BooleanField(default=choices.DEFAULT_IGNORE_CASE, required=False, help_text=f"Ignore case while matching? Default = {choices.DEFAULT_IGNORE_CASE}.")
    ignore_punctuation = serializers.BooleanField(default=choices.DEFAULT_IGNORE_PUNCTUATION, required=False, help_text=f"If set False, end-of-sentence characters between lexicon entry words and/or counter lexicon entries, nullify the effect. Default = {choices.DEFAULT_IGNORE_PUNCTUATION}.")
    url = serializers.SerializerMethodField()
    tagger_groups = serializers.SerializerMethodField(read_only=True)
    task = TaskSerializer(read_only=True)


    def get_tagger_groups(self, value: RegexTagger):
        tgs = RegexTaggerGroup.objects.filter(regex_taggers__project_id=value.project.pk, regex_taggers__id=value.pk)
        descriptions = [{"tagger_group_id": tagger.pk, "description": tagger.description} for tagger in tgs]
        return descriptions


    class Meta:
        model = RegexTagger
        fields = ('id', 'url', 'author',
                  'description', 'lexicon', 'counter_lexicon', 'operator', 'match_type', 'required_words',
                  'phrase_slop', 'counter_slop', 'n_allowed_edits', 'return_fuzzy_match', 'ignore_case',
                  'ignore_punctuation', 'phrase_slop', 'counter_slop', 'n_allowed_edits', 'return_fuzzy_match',
                  'ignore_case', 'ignore_punctuation', 'tagger_groups', 'task')
        fields_to_parse = ('lexicon', 'counter_lexicon')


class RegexTaggerTagTextsSerializer(serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True))


class TagRandomDocSerializer(IndicesSerializerMixin):
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class RegexTaggerTagDocsSerializer(serializers.Serializer):
    docs = serializers.ListField(child=serializers.JSONField(), help_text="List of JSON documents to tag.")
    fields = serializers.ListField(child=serializers.JSONField(), help_text="Dot separated paths of the JSON document to the text you wish to tag.")


class ApplyRegexTaggerSerializer(FieldParseSerializer, IndicesSerializerMixin):
    description = serializers.CharField(required=True, help_text=f"Text for distinguishing this task from others.")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text=f"Which fields to extract the text from.")
    query = serializers.JSONField(help_text=f"Filter the documents which to scroll and apply to.", default=EMPTY_QUERY)
    bulk_size = serializers.IntegerField(min_value=1, max_value=10000, default=choices.DEFAULT_BULK_SIZE, help_text=f"How many documents should be sent towards Elasticsearch at once. Default = {choices.DEFAULT_BULK_SIZE}")
    max_chunk_bytes = serializers.IntegerField(min_value=1, default=choices.DEFAULT_MAX_CHUNK_BYTES, help_text=f"Data size in bytes that Elasticsearch should accept to prevent Entity Too Large errors. Default = {choices.DEFAULT_MAX_CHUNK_BYTES}.")
    es_timeout = serializers.IntegerField(default=choices.DEFAULT_ES_TIMEOUT, help_text=f"Elasticsearch scroll timeout in minutes. Default = {choices.DEFAULT_ES_TIMEOUT}.")
    new_fact_name = serializers.CharField(required=False, default="", help_text=f"Used as fact name when applying the tagger. Defaults to tagger description.")
    new_fact_value = serializers.CharField(required=False, default="", help_text=f"Used as fact value when applying the tagger. Defaults to tagger match.")
    add_spans = serializers.BooleanField(required=False, default=choices.DEFAULT_ADD_SPANS, help_text=f"If enabled, spans of detected matches are added to texta facts and corresponding facts can be highlighted in Searcher. Default = {choices.DEFAULT_ADD_SPANS}")


class RegexTaggerGroupTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField(help_text=f'Document in JSON format.')
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class RegexGroupTaggerTagTextSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=True, required=True)


class RegexMultitagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    taggers = serializers.ListField(
        help_text='List of RegexTagger IDs to be used. Default: [] (uses all).',
        child=serializers.IntegerField(),
        default=[]
    )


class RegexTaggerGroupSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()
    url = serializers.SerializerMethodField()
    task = TaskSerializer(read_only=True)
    author = UserSerializer(read_only=True)
    tagger_info = serializers.SerializerMethodField(read_only=True)  # Helper field for displaying tagger info in a friendly manner.


    def get_tagger_info(self, value: RegexTaggerGroup):
        serializer = RegexTaggerSerializer(value.regex_taggers.all(), many=True, context={"request": self.context["request"]})
        return serializer.data


    class Meta:
        model = RegexTaggerGroup
        # regex_taggers is the field which to use to manipulate the related RegexTagger model objects.
        fields = ('id', 'url', 'regex_taggers', 'author', 'task', 'description', 'tagger_info')


class RegexTaggerGroupMultitagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    tagger_groups = serializers.ListField(
        help_text='List of RegexTaggerGroup IDs to be used. Default: [] (uses all).',
        child=serializers.IntegerField(),
        default=[]
    )


class RegexTaggerGroupMultitagDocsSerializer(serializers.Serializer):
    docs = serializers.ListField(child=serializers.JSONField())
    fields = serializers.ListField(child=serializers.CharField())
    tagger_groups = serializers.ListField(
        help_text='List of RegexTaggerGroup IDs to be used. Default: [] (uses all).',
        child=serializers.IntegerField(),
        default=[]
    )


class ApplyRegexTaggerGroupSerializer(FieldParseSerializer, IndicesSerializerMixin):
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text="Which fields to extract the text from.")
    query = serializers.JSONField(help_text='Filter the documents which to scroll and apply to.', default=EMPTY_QUERY)
    es_timeout = serializers.IntegerField(default=choices.DEFAULT_ES_TIMEOUT, help_text=f"Elasticsearch scroll timeout in minutes. Default = {choices.DEFAULT_ES_TIMEOUT}.")
    bulk_size = serializers.IntegerField(min_value=1, max_value=10000, default=choices.DEFAULT_BULK_SIZE, help_text=f"How many documents should be sent towards Elasticsearch at once. Default = {choices.DEFAULT_BULK_SIZE}.")
    max_chunk_bytes = serializers.IntegerField(min_value=1, default=choices.DEFAULT_MAX_CHUNK_BYTES, help_text=f"Data size in bytes that Elasticsearch should accept to prevent Entity Too Large errors. Default = {choices.DEFAULT_MAX_CHUNK_BYTES}.")
