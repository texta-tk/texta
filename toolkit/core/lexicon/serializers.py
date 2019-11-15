from rest_framework import serializers
import json

from toolkit.core.lexicon.models import Lexicon
from toolkit.serializer_constants import FieldParseSerializer


class StringListField(serializers.ListField):
    child = serializers.CharField()


class LexiconSerializer(FieldParseSerializer, serializers.ModelSerializer):
    phrases = StringListField(help_text=f'Phrases as list of strings.', required=False)
    discarded_phrases = StringListField(help_text=f'Discarded phrases as list of strings.', required=False)


    class Meta:
        model = Lexicon
        fields = ('id', 'author', 'description', 'phrases', 'discarded_phrases')
        read_only_fields = ('project', 'author')
        fields_to_parse = ('phrases', 'discarded_phrases')
