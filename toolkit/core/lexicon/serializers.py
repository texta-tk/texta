from rest_framework import serializers
import json

from toolkit.core.lexicon.models import Lexicon


class LexiconSerializer(serializers.ModelSerializer):

    # If we want to enable PUT here, we can't have it write_only
    phrases = serializers.ListField(child=serializers.CharField(),
                                    help_text=f'Phrases as list of strings.',
                                    required=False)
    discarded_phrases = serializers.ListField(child=serializers.CharField(),
                                              help_text=f'Discarded phrases as list of strings.',
                                              required=False)
    phrases_parsed = serializers.SerializerMethodField()
    discarded_phrases_parsed = serializers.SerializerMethodField(required=False)

    class Meta:
        model = Lexicon
        fields = ('id', 'author', 'description', 'phrases', 'discarded_phrases', 'phrases_parsed', 'discarded_phrases_parsed')
        read_only_fields = ('project', 'author', 'phrases_parsed', 'discarded_phrases_parsed')

    def get_phrases_parsed(self, obj):
        print(obj.phrases)
        try:
            return json.loads(obj.phrases)
        except:
            return None

    def get_discarded_phrases_parsed(self, obj):
        try:
            return json.loads(obj.discarded_phrases)
        except:
            return None
