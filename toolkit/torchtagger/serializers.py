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

    model_architecture = serializers.ChoiceField(choices=choices.MODEL_CHOICES)
    maximum_sample_size = serializers.IntegerField(default=10000, required=False)

    task = TaskSerializer(read_only=True)
    plot = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()

    class Meta:
        model = TorchTagger
        fields = (
            'url', 'author_username', 'id', 'description', 'fields', 'embedding',
            'model_architecture', 'maximum_sample_size', 'location', 'plot', 'task'
        )
        
        read_only_fields = ('project', 'fields_parsed', 'location', 'plot', 'task')
