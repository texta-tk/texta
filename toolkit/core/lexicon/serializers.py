from rest_framework import serializers
import json

from toolkit.core.lexicon.models import Lexicon


class StringListField(serializers.ListField):
    child = serializers.CharField()


class LexiconSerializer(serializers.ModelSerializer):
    phrases = StringListField(help_text=f'Phrases as list of strings.', required=False)
    discarded_phrases = StringListField(help_text=f'Discarded phrases as list of strings.', required=False)
    phrases_parsed = serializers.SerializerMethodField()
    discarded_phrases_parsed = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Lexicon
        fields = ('id', 'author', 'description', 'phrases', 'discarded_phrases', 'phrases_parsed', 'discarded_phrases_parsed')
        read_only_fields = ('project', 'author')

    def get_phrases_parsed(self, obj):
        try:
            if isinstance(obj.phrases, str):
                obj.phrases = eval(obj.phrases)
            return obj.phrases
        except:
            return None

    def get_discarded_phrases_parsed(self, obj):
        try:
            if isinstance(obj.discarded_phrases, str):
                obj.discarded_phrases = eval(obj.discarded_phrases)
            return obj.discarded_phrases
        except:
            return None
