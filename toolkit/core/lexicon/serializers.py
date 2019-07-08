from rest_framework import serializers

from toolkit.core.lexicon.models import Lexicon

class LexiconSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lexicon
        fields = ('id', 'author', 'description', 'phrases')
        read_only_fields = ('project', 'author')
