from toolkit.serializer_constants import ProjectResourceUrlSerializer
from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.choices import get_index_choices
from toolkit.elastic.models import Reindexer
from rest_framework import serializers
import json


class ReindexerCreateSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    url = serializers.SerializerMethodField()
    description = serializers.CharField(help_text='Describe your re-indexing task', required=True, allow_blank=False)
    indices = serializers.ListField(child=serializers.CharField(), help_text=f'Indices to reindex.', write_only=True, required=True)
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields to add to reindexed index.', write_only=True)
    query = serializers.SerializerMethodField()
    new_index = serializers.CharField(help_text='Your new re-indexed index name', allow_blank=False, required=True)
    field_type = serializers.ListField(child=serializers.DictField(child=serializers.CharField()), help_text=f'Used to update field types.', required=False)
    task = TaskSerializer(read_only=True)

    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'description', 'indices', 'fields', 'query', 'new_index', 'random_size', 'field_type', 'task')

    def get_query(self, obj):
        if obj.query:
            return json.loads(obj.query)
        return None

