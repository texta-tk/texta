from typing import List

from rest_framework import serializers
from texta_elastic.core import ElasticCore

from toolkit.core.project.models import Project
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.elastic.validators import (
    check_for_banned_beginning_chars,
    check_for_colons,
    check_for_special_symbols,
    check_for_upper_case,
    check_for_wildcards
)
from toolkit.serializer_constants import CommonModelSerializerMixin, FieldParseSerializer, ProjectResourceUrlSerializer


class ReindexerCreateSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer, CommonModelSerializerMixin):
    url = serializers.SerializerMethodField()
    scroll_size = serializers.IntegerField(min_value=0, max_value=10000, required=False)  # Max value stems from Elasticsearch max doc count limitation.
    indices = serializers.ListField(child=serializers.CharField(), help_text=f'Add the indices, you wish to reindex into a new index.', required=True)
    query = serializers.JSONField(help_text='Add a query, if you wish to filter the new reindexed index.', required=False)
    new_index = serializers.CharField(help_text='Your new re-indexed index name', allow_blank=False, required=True,
                                      validators=[
                                          check_for_wildcards,
                                          check_for_colons,
                                          check_for_special_symbols,
                                          check_for_banned_beginning_chars,
                                          check_for_upper_case
                                      ])
    field_type = serializers.ListField(help_text=f'Used to update the fieldname and the field type of chosen paths.', required=False)
    add_facts_mapping = serializers.BooleanField(help_text='Add texta facts mapping. NB! If texta_facts is present in reindexed fields, the mapping is always created.', required=False, default=True)
    fields = serializers.ListField(
        child=serializers.CharField(),
        help_text=f'Empty fields chooses all posted indices fields. Fields content adds custom field content to the new index.',
        required=False
    )
    random_size = serializers.IntegerField(
        help_text='Picks a subset of documents of chosen size at random. Disabled by default.',
        required=False,
        min_value=1,
    )


    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'author', 'description', 'indices', 'scroll_size', 'fields', 'query', 'new_index', 'random_size', 'field_type', 'add_facts_mapping', 'tasks')
        fields_to_parse = ('fields', 'field_type', 'indices')


    def validate_new_index(self, value):
        """ Check that new_index does not exist """
        if value in ElasticCore().get_indices():
            raise serializers.ValidationError("new_index already exists, choose a different name for your reindexed index")
        return value


    def validate_indices(self, value):
        """ check if re-indexed index is in the relevant project indices field """
        project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        for index in value:
            indices = project_obj.get_indices()
            if index not in indices:
                raise serializers.ValidationError(f'Index "{index}" is not contained in your project indices "{indices}"')
        return value


    def validate_fields(self, value: List[str]):
        """ check if changed fields included in the request are in the relevant project fields """
        project_obj: Project = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        indices = self.context["request"].data.get("indices", [])
        indices = project_obj.get_available_or_all_project_indices(indices)
        project_fields = ElasticCore().get_fields(indices=indices)
        field_data = [field["path"] for field in project_fields]
        for field in value:
            if field not in field_data:
                raise serializers.ValidationError(f'The fields you are attempting to re-index are not in current project fields: {project_fields}')
        return value
