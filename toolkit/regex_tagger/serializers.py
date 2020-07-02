from rest_framework import serializers

from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from texta_lexicon_matcher.lexicon_matcher import SUPPORTED_MATCH_TYPES, SUPPORTED_OPERATIONS
#from .choices import OPERATOR_CHOICES, MATCH_TYPE_CHOICES
from .models import RegexTagger

class RegexTaggerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer, FieldParseSerializer):
    description = serializers.CharField()
    lexicon = serializers.ListField(child=serializers.CharField(required=True))
    counter_lexicon = serializers.ListField(child=serializers.CharField(required=False), default=[])

    operator = serializers.CharField(default=SUPPORTED_OPERATIONS[0], required=False)
    match_type = serializers.CharField(default=SUPPORTED_MATCH_TYPES[0], required=False)
    required_words = serializers.FloatField(default=1.0, required=False)
    phrase_slop = serializers.IntegerField(default=0, required=False)
    counter_slop = serializers.IntegerField(default=0, required=False)
    n_allowed_edits = serializers.IntegerField(default=0, required=False)
    return_fuzzy_match = serializers.BooleanField(default=True, required=False)
    ignore_case = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = RegexTagger
        fields = ('id', #'url',
                  'description', 'lexicon', 'counter_lexicon', 'operator', 'match_type', 'required_words',
                  'phrase_slop', 'counter_slop', 'n_allowed_edits', 'return_fuzzy_match', 'ignore_case')


class RegexTaggerTagTextsSerializer(serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True))

class RegexMultitagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
    taggers = serializers.ListField(help_text='List of RegexTagger IDs to be used. Default: [] (uses all).',
                                    child=serializers.IntegerField(),
                                    default=[])
