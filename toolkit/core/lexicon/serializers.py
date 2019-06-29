from rest_framework import serializers

from toolkit.core.lexicon.models import Lexicon

class LexiconSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Lexicon
        fields = ('url', 'id', 'project', 'author', 'description', 'phrases')
        read_only_fields = ('project', 'author')
