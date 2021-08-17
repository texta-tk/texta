from rest_framework import serializers
import json

from toolkit.core.lexicon.models import Lexicon
from toolkit.serializer_constants import FieldParseSerializer


class StringListField(serializers.ListField):
    child = serializers.CharField()


class LexiconSerializer(FieldParseSerializer, serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.profile.get_display_name', read_only=True)
    positives_used = StringListField(help_text=f'Positive phrases for the model as list of strings. Default: EMPTY', required=False)
    negatives_used = StringListField(help_text=f'Negative phrases for the model as list of strings. Default: EMPTY', required=False)
    positives_unused = StringListField(help_text=f'Positive phrases in the lexicon, not used in mining as list of strings. Default: EMPTY', required=False,)
    negatives_unused = StringListField(help_text=f'Negative phrases left out from the lexicon, not used in mining as list of strings. Default: EMPTY', required=False)
    

    class Meta:
        model = Lexicon
        fields = ('id', 'author', 'description', 'positives_used', 'negatives_used', 'positives_unused', 'negatives_unused', 'author_username')
        read_only_fields = ('project', 'author', 'author_username')
        fields_to_parse = ('positives_used', 'negatives_used', 'positives_unused', 'negatives_unused')
