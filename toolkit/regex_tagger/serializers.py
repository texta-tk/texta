from rest_framework import serializers

from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from .choices import OPERATOR_CHOICES, MATCH_TYPE_CHOICES
from .models import RegexTagger

class RegexTaggerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer, FieldParseSerializer):
    description = serializers.CharField()
    lexicon = serializers.ListField(child=serializers.CharField(required=True))
    counter_lexicon = serializers.ListField(child=serializers.CharField(required=False), default=[])

    operator = serializers.CharField(default=OPERATOR_CHOICES[0][0], required=False)
    match_type = serializers.CharField(default=MATCH_TYPE_CHOICES[0][0], required=False)
    required_words = serializers.FloatField(default=0.0, required=False)
    phrase_slop = serializers.IntegerField(default=0, required=False)
    counter_slop = serializers.IntegerField(default=0, required=False)
    return_fuzzy_match = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = RegexTagger
        fields = ('id', #'url', 
                    'description', 'lexicon', 'counter_lexicon', 'operator', 'match_type', 'required_words',
                  'phrase_slop', 'counter_slop', 'return_fuzzy_match')


class RegexTaggerTagTextsSerializer(serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True))
