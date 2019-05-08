from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.models import Project, Search, Lexicon, Phrase, Task, UserProfile
from toolkit.core.choices import get_index_choices


class TaskSerializer(serializers.HyperlinkedModelSerializer):
    status = serializers.CharField(read_only=True)
    progress = serializers.FloatField(read_only=True)
    step = serializers.CharField(read_only=True)
    time_started = serializers.DateTimeField(read_only=True)
    last_update = serializers.DateTimeField(read_only=True)
    time_completed = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Task
        fields = ('id', 'status', 'progress', 'step', 'time_started', 'last_update', 'time_completed')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.EmailField(source='user.email')
    date_joined = serializers.ReadOnlyField(source='user.date_joined')

    class Meta:
        model = UserProfile
        fields = ('url', 'id', 'username', 'email', 'active_project', 'date_joined') #'__all__'


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    from toolkit.embedding.serializers import EmbeddingSerializer
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    embeddings = EmbeddingSerializer(read_only=True, many=True)

    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices', 'embeddings')


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
