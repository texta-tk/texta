from toolkit.serializer_constants import ProjectResourceUrlSerializer
from toolkit.elastic.models import Reindexer
from rest_framework import serializers
from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.choices import get_index_choices
import json

# TODO filter choices
class ReindexerCreateSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    """ implements for new indices objects ->
        (1) subsets of existing indices,
        (2) with types (mapping collections) changed
        (3) with field names renamed
        (4) subsets of existing indices by using the 'search' feature. """

    url = serializers.SerializerMethodField()
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    fields_parsed = serializers.SerializerMethodField()
    # task = TaskSerializer(read_only=True)

    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'description', 'indices', 'fields', 'fields_parsed')

    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None


class ReindexerUpdateSerializer(serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    """ implements for updating indices objects ->
        (1) subsets of existing indices,
        (2) with types (mapping collections) changed
        (3) with field names renamed
        (4) subsets of existing indices by using the 'search' feature. """

    url = serializers.SerializerMethodField()
    indices = serializers.MultipleChoiceField(choices=get_index_choices())
    fields = serializers.ListField(child=serializers.CharField(), help_text=f'Fields used to build the model.', write_only=True)
    fields_parsed = serializers.SerializerMethodField()
    # task = TaskSerializer(read_only=True)

    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'description', 'indices', 'fields', 'fields_parsed')

    def get_fields_parsed(self, obj):
        if obj.fields:
            return json.loads(obj.fields)
        return None


