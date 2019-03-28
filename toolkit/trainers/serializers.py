from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.trainers.models import Embedding, Tagger, Task
from toolkit.elastic.utils import get_field_choices
from toolkit.trainers.choices import MODEL_CHOICES


class TaskSerializer(serializers.HyperlinkedModelSerializer):
    status = serializers.CharField(read_only=True)
    progress = serializers.FloatField(read_only=True)
    progress_message = serializers.CharField(read_only=True)
    time_started = serializers.DateTimeField(read_only=True)
    last_update = serializers.DateTimeField(read_only=True)
    time_completed = serializers.DateTimeField(read_only=True)
    task_type = serializers.ChoiceField(choices=[(a, a) for a in MODEL_CHOICES.keys()])

    class Meta:
        model = Task
        fields = ('id', 'task_type', 'status', 'progress', 'progress_message', 'time_started', 'last_update', 'time_completed')


class EmbeddingSerializer(serializers.HyperlinkedModelSerializer):
    vocab_size = serializers.IntegerField(read_only=True)
    location = serializers.CharField(read_only=True)
    task = TaskSerializer(read_only=True)
    fields = serializers.MultipleChoiceField(choices=get_field_choices())
    num_dimensions = serializers.ChoiceField(choices=MODEL_CHOICES['embedding']['num_dimensions'])
    max_vocab = serializers.ChoiceField(choices=MODEL_CHOICES['embedding']['max_vocab'])
    min_freq = serializers.ChoiceField(choices=MODEL_CHOICES['embedding']['min_freq'])

    class Meta:
        model = Embedding
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'num_dimensions', 'max_vocab', 'min_freq', 'vocab_size', 'location', 'task')


class TaggerSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Tagger
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'datasets')

