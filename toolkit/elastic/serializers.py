from toolkit.serializer_constants import ProjectResourceUrlSerializer
from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.choices import get_index_choices
from toolkit.elastic.models import Reindexer
from rest_framework import serializers
import json


class ReindexerCreateSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    url = serializers.SerializerMethodField()
    indices = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True, required=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    fields_parsed = serializers.SerializerMethodField()
    task = TaskSerializer(read_only=True)

    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'description', 'indices', 'fields', 'task', 'fields_parsed', 'new_index')
        extra_kwargs = {'description': {'required': True}, 'new_index': {'required': True}}

    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None


class ReindexerUpdateSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    url = serializers.SerializerMethodField()
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    fields_parsed = serializers.SerializerMethodField()
    task = TaskSerializer(read_only=True)

    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'description', 'indices', 'fields', 'fields_parsed')

    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None


