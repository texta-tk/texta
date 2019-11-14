import json
import re
from rest_framework import serializers

from toolkit.torchtagger import choices
from toolkit.torchtagger.models import TorchTagger
from toolkit.constants import get_field_choices
from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import ProjectResourceUrlSerializer


class TorchTaggerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.')
    query = serializers.JSONField(help_text='Query in JSON format', required=False)

    model_architecture = serializers.ChoiceField(choices=choices.MODEL_CHOICES)
    maximum_sample_size = serializers.IntegerField(default=10000, required=False)
    num_epochs = serializers.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, required=False)

    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = TorchTagger
        fields = (
            'url', 'author_username', 'id', 'description', 'query', 'fields', 'embedding', 'f1_score', 'precision', 'recall', 'accuracy',
            'model_architecture', 'maximum_sample_size', 'num_epochs', 'location', 'plot', 'task'
        )
        
        read_only_fields = ('project', 'fields_parsed', 'f1_score', 'precision', 'recall', 'accuracy', 'location', 'plot', 'task')
