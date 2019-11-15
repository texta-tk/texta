from toolkit.serializer_constants import ProjectResourceUrlSerializer
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.models import Reindexer
from rest_framework import serializers
import json


class ReindexerCreateSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    url = serializers.SerializerMethodField()
    description = serializers.CharField(help_text='Describe your re-indexing task', required=True, allow_blank=False)
    indices = serializers.ListField(child=serializers.CharField(), help_text=f'Add the indices, you wish to reindex into a new index.', write_only=True, required=True)
    fields = serializers.ListField(child=serializers.CharField(),
                                   help_text=f'Empty fields chooses all posted indices fields. Fields content adds custom field content to the new index.',
                                   write_only=True)
    query = serializers.JSONField(help_text='Add a query, if you wish to filter the new reindexed index.', required=False)
    field_type_parsed = serializers.SerializerMethodField(help_text="This field stores field_type POST content as string.")
    new_index = serializers.CharField(help_text='Your new re-indexed index name', allow_blank=False, required=True)
    random_size = serializers.IntegerField(help_text='By default, random document add is not applied. If you want this feature applied, define a random size value.', required=False)
    field_type = serializers.ListField(help_text=f'Used to update the fieldname and the field type of chosen paths.',
        required=False,
        write_only=True)
    task = TaskSerializer(read_only=True)

    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'author_username', 'description', 'indices', 'fields', 'query', 'new_index', 'random_size', 'field_type', 'task', 'field_type_parsed')

    def get_field_type_parsed(self, obj):
        if obj.field_type:
            return json.loads(obj.field_type)
        return None
