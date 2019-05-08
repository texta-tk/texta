from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.core.models import Project, Search, Lexicon, Phrase, Task, UserProfile
from toolkit.core.choices import get_index_choices


class UserSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.EmailField(source='user.email')
    date_joined = serializers.ReadOnlyField(source='user.date_joined')

    class Meta:
        model = UserProfile
        fields = ('url', 'id', 'username', 'email', 'active_project', 'date_joined') #'__all__'


class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices')


from rest_framework_nested.relations import NestedHyperlinkedRelatedField

class ProjectSerializer(serializers.HyperlinkedModelSerializer):
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    class Meta:
        model = Project
        fields = ('url', 'id', 'title', 'owner', 'users', 'indices', 'embedding')

    embedding = serializers.HyperlinkedIdentityField(
            read_only=True,
            view_name='project-embedding-list',
            lookup_url_kwarg='project_pk'
    )
    #embedding = NestedHyperlinkedRelatedField(
    #    many=True,
    #    read_only=True,   # Or add a queryset
    #    view_name='embedding',
    #    parent_lookup_kwargs={'project_pk': 'project_pk'}
    #)

    #tagger = serializers.HyperlinkedIdentityField(
    #        read_only=True,
    #        view_name='project-tagger-list',
    #        lookup_url_kwarg='project_pk'
    #)

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
