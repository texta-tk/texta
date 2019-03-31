from django.contrib.auth.models import User
from rest_framework import serializers

from toolkit.trainer.models import Embedding, Tagger, Task
from toolkit.trainer.choices import MODEL_CHOICES, get_field_choices, get_classifier_choices, get_vectorizer_choices


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


class EmbeddingSerializer(serializers.HyperlinkedModelSerializer):
    vocab_size = serializers.IntegerField(read_only=True)
    location = serializers.CharField(read_only=True)
    task = TaskSerializer(read_only=True)
    fields = serializers.MultipleChoiceField(choices=get_field_choices())
    num_dimensions = serializers.ChoiceField(choices=MODEL_CHOICES['embedding']['num_dimensions'])
    max_vocab = serializers.ChoiceField(choices=MODEL_CHOICES['embedding']['max_vocab'])
    min_freq = serializers.ChoiceField(choices=MODEL_CHOICES['embedding']['min_freq'])
    vocab_size = serializers.IntegerField(read_only=True)

    class Meta:
        model = Embedding
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'num_dimensions', 'max_vocab', 'min_freq', 'vocab_size', 'location', 'task')


class TaggerSerializer(serializers.HyperlinkedModelSerializer):
    fields = serializers.MultipleChoiceField(choices=get_field_choices())
    vectorizer = serializers.ChoiceField(choices=get_vectorizer_choices())
    classifier = serializers.ChoiceField(choices=get_classifier_choices())
    #negative_multiplier = serializers.ChoiceField(choices=MODEL_CHOICES['tagger']['negative_multiplier'])
    maximum_sample_size = serializers.ChoiceField(choices=MODEL_CHOICES['tagger']['max_sample_size'])
    task = TaskSerializer(read_only=True)
    location = serializers.CharField(read_only=True)
    statistics = serializers.CharField(read_only=True)

    class Meta:
        model = Tagger
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'embedding', 'vectorizer', 'classifier', 'maximum_sample_size', 'location', 'statistics', 'task')

