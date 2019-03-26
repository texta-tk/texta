from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.models import Project, Dataset, Search, Model, Lexicon, Phrase


class UserSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email')


class ProjectSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'datasets')


class DatasetSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Dataset
        fields = ('url', 'id', 'index', 'owner')


class SearchSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Search
        fields = ('url', 'id', 'description', 'query', 'author', 'project')


class ModelSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Model
        fields = ('url', 'id', 'description', 'model_type', 'status', 'parameters', 'result')


class PhraseSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Phrase
        fields = ('url', 'id', 'lexicon', 'phrase')


class LexiconSerializer(serializers.HyperlinkedModelSerializer):
    phrases = PhraseSerializer(read_only=True)
    class Meta:
        model = Lexicon
        fields = ('url', 'id', 'description', 'author', 'phrases')
