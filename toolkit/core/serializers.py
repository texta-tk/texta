from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.models import Project, Search, Lexicon, Phrase
from toolkit.elastic.utils import get_indices


class UserSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email')


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    indices = serializers.MultipleChoiceField(choices=get_indices())
    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices')


class SearchSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Search
        fields = ('url', 'id', 'description', 'query', 'author', 'project')


class PhraseSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Phrase
        fields = ('url', 'id', 'project', 'author', 'phrase')


class LexiconSerializer(serializers.HyperlinkedModelSerializer):
    phrases = PhraseSerializer(read_only=True)
    class Meta:
        model = Lexicon
        fields = ('url', 'id', 'project', 'author', 'description', 'phrases')
