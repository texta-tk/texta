import json
import re
from rest_framework import serializers

from toolkit.torchtagger import choices
from toolkit.torchtagger.models import TorchTagger
from toolkit.constants import get_field_choices
from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import ProjectResourceUrlSerializer, FieldParseSerializer


class TorchTaggerSerializer(FieldParseSerializer, serializers.ModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    query = serializers.JSONField(help_text='Query in JSON format', required=False)
    fact_name = serializers.CharField(default=None, required=False, help_text=f'Fact name used to filter tags (fact values). Default: None')
    model_architecture = serializers.ChoiceField(choices=choices.MODEL_CHOICES)
    maximum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, required=False)
    minimum_sample_size = serializers.IntegerField(default=choices.DEFAULT_MIN_SAMPLE_SIZE, required=False)
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, required=False)

    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = TorchTagger
        fields = (
            'url', 'author_username', 'id', 'description', 'query', 'fields', 'embedding', 'f1_score', 'precision', 'recall', 'accuracy',
            'model_architecture', 'maximum_sample_size', 'minimum_sample_size', 'num_epochs', 'plot', 'task', 'fact_name', 'epoch_reports',
        )
        read_only_fields = ('project', 'fields', 'f1_score', 'precision', 'recall', 'accuracy', 'plot', 'task' ,'fact_name', 'epoch_reports')
        fields_to_parse = ('fields', 'epoch_reports')
