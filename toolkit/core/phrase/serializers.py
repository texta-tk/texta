from rest_framework import serializers

from toolkit.core.phrase.models import Phrase

class PhraseSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Phrase
        fields = ('url', 'id', 'project', 'author', 'phrase')
