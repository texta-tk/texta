from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.models import Project, Dataset, Search, Lexicon, Phrase, Embedding, Tagger


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


class PhraseSerializer(serializers.HyperlinkedModelSerializer):
    
    class Meta:
        model = Phrase
        fields = ('url', 'id', 'lexicon', 'phrase')


class LexiconSerializer(serializers.HyperlinkedModelSerializer):
    phrases = PhraseSerializer(read_only=True)
    class Meta:
        model = Lexicon
        fields = ('url', 'id', 'project', 'author', 'description', 'phrases')


class EmbeddingSerializer(serializers.HyperlinkedModelSerializer):
    vocab_size = serializers.IntegerField(read_only=True)
    location = serializers.CharField(read_only=True)
    task = serializers.RelatedField(read_only=True)

    class Meta:
        model = Embedding
        fields = ('url', 'id', 'description', 'num_dimensions', 'max_vocab', 'vocab_size', 'location', 'task')


class TaggerSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Tagger
        fields = ('url', 'id', 'description')
