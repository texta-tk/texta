from rest_framework import serializers

from toolkit.tagger.models import Tagger, Task
from toolkit.tagger.choices import TAGGER_CHOICES, get_field_choices, get_classifier_choices, get_vectorizer_choices
from toolkit.core.task.serializers import TaskSerializer


class TaggerSerializer(serializers.ModelSerializer):
    fields = serializers.MultipleChoiceField(choices=get_field_choices(), required=True)
    vectorizer = serializers.ChoiceField(choices=get_vectorizer_choices())
    classifier = serializers.ChoiceField(choices=get_classifier_choices())
    #negative_multiplier = serializers.ChoiceField(choices=MODEL_CHOICES['tagger']['negative_multiplier'])
    maximum_sample_size = serializers.ChoiceField(choices=TAGGER_CHOICES['max_sample_size'])

    task = TaskSerializer(read_only=True)

    class Meta:
        model = Tagger
        fields = ('url', 'id', 'description', 'project', 'author', 'query', 'fields', 'embedding', 'vectorizer', 'classifier', 'maximum_sample_size', 'location', 'precision', 'recall', 'f1_score', 'confusion_matrix', 'task')
        read_only_fields = ('author', 'project', 'location', 'precision', 'recall', 'f1_score', 'confusion_matrix')


class SimpleTaggerSerializer(serializers.ModelSerializer):

    class Meta:
        model = Tagger
        fields = ('id', 'description')


class TextSerializer(serializers.Serializer):
    text = serializers.CharField()


class DocSerializer(serializers.Serializer):
    doc = serializers.JSONField()
