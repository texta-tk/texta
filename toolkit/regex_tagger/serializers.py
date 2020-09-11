from rest_framework import serializers
from texta_lexicon_matcher.lexicon_matcher import SUPPORTED_MATCH_TYPES, SUPPORTED_OPERATORS

from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from .models import RegexTagger, RegexTaggerGroup
from ..core.task.serializers import TaskSerializer
from ..elastic.searcher import EMPTY_QUERY
from ..elastic.serializers import IndexSerializer


PRIORITY_CHOICES = (
    ("first_span", "first_span"),
    ("last_span", "last_span"),
)

MATCH_TYPE_CHOICES = [(match_type, match_type) for match_type in SUPPORTED_MATCH_TYPES]
OPERATOR_CHOICES = [(operator, operator) for operator in SUPPORTED_OPERATORS]


class RegexTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()
    author_username = serializers.CharField(source='author.username', read_only=True)
    lexicon = serializers.ListField(child=serializers.CharField(required=True), help_text="Words/phrases/regex patterns to match.")
    counter_lexicon = serializers.ListField(child=serializers.CharField(required=False), default=[], help_text="Words/phrases/regex patterns to nullify lexicon matches. Default=[]")

    operator = serializers.ChoiceField(default=SUPPORTED_OPERATORS[0], choices=OPERATOR_CHOICES, required=False, help_text="Logical operation between lexicon entries. Choices = ['and', 'or']. Default='or'")
    match_type = serializers.ChoiceField(default=SUPPORTED_MATCH_TYPES[0], choices=MATCH_TYPE_CHOICES, required=False, help_text="How to match lexicon entries to text. Choices = ['prefix', 'exact', 'subword']. Default='prefix'")
    required_words = serializers.FloatField(default=1.0, required=False, help_text="Required ratio of lexicon entries matched in text for returning a positive result. NB! Only takes effect if operator=='and'. Default=1.0")
    phrase_slop = serializers.IntegerField(default=0, required=False, help_text="Number of non-lexicon words allowed between the words of one lexicon entry. Default=0")
    counter_slop = serializers.IntegerField(default=0, required=False, help_text="Number of words allowed between lexicon entries and counter lexicon entries for the latter to have effect. Default=0")
    n_allowed_edits = serializers.IntegerField(default=0, required=False, help_text="Number of allowed character changes between lexicon entries and candidate matches in text. Default=0.")
    return_fuzzy_match = serializers.BooleanField(default=True, required=False, help_text="Return fuzzy match (opposed to exact lexicon entry)? Default=True")
    ignore_case = serializers.BooleanField(default=True, required=False, help_text="Ignore case while matching? Default=True")
    ignore_punctuation = serializers.BooleanField(default=True, required=False, help_text="If set False, end-of-sentence characters between lexicon entry words and/or counter lexicon entries, nullify the effect. Default=True")
    url = serializers.SerializerMethodField()
    tagger_groups = serializers.SerializerMethodField(read_only=True)


    def get_tagger_groups(self, value: RegexTagger):
        tgs = RegexTaggerGroup.objects.filter(regex_taggers__project_id=value.project.pk, regex_taggers__id=value.pk)
        descriptions = [{"tagger_group_id": tagger.pk, "description": tagger.description} for tagger in tgs]
        return descriptions


    class Meta:
        model = RegexTagger
        fields = ('id', 'url', 'author_username',
                  'description', 'lexicon', 'counter_lexicon', 'operator', 'match_type', 'required_words',
                  'phrase_slop', 'counter_slop', 'n_allowed_edits', 'return_fuzzy_match', 'ignore_case',
                  'ignore_punctuation', 'phrase_slop', 'counter_slop', 'n_allowed_edits', 'return_fuzzy_match', 'ignore_case', 'ignore_punctuation', 'tagger_groups')
        fields_to_parse = ('lexicon', 'counter_lexicon')


class RegexTaggerTagTextsSerializer(serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True))


class TagRandomDocSerializer(serializers.Serializer):
    indices = IndexSerializer(many=True, default=[])
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class RegexTaggerGroupTagDocumentSerializer(serializers.Serializer):
    doc = serializers.JSONField(help_text=f'Document in JSON format.')
    fields = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)


class RegexGroupTaggerTagTextSerializer(serializers.Serializer):
    text = serializers.CharField(required=True)


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
    author_username = serializers.CharField(source='author.username', read_only=True)
    tagger_info = serializers.SerializerMethodField(read_only=True)  # Helper field for displaying tagger info in a friendly manner.


    def get_tagger_info(self, value: RegexTaggerGroup):
        return [tagger.get_description() for tagger in value.regex_taggers.all()]


    class Meta:
        model = RegexTaggerGroup
        # regex_taggers is the field which to use to manipulate the related RegexTagger model objects.
        fields = ('id', 'url', 'regex_taggers', 'author_username', 'task', 'description', 'tagger_info')


class RegexTaggerGroupMultitagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    tagger_groups = serializers.ListField(
        help_text='List of RegexTaggerGroup IDs to be used. Default: [] (uses all).',
        child=serializers.IntegerField(),
        default=[]
    )


class ApplyRegexTaggerGroupSerializer(FieldParseSerializer, serializers.Serializer):
    description = serializers.CharField(required=True, help_text="Text for distinguishing this task from others.")
    # priority = serializers.ChoiceField(default=None, choices=PRIORITY_CHOICES)
    indices = IndexSerializer(many=True, default=[], help_text="Which indices in the project to apply this to.")
    fields = serializers.ListField(required=True, child=serializers.CharField(), help_text="Which fields to extract the text from.")
    query = serializers.JSONField(help_text='Filter the documents which to scroll and apply to.', default=EMPTY_QUERY)
