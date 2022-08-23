import json

from rest_framework import serializers
from texta_elastic.core import ElasticCore

from toolkit.core.project.models import Project
from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.choices import LABEL_DISTRIBUTION
from toolkit.elastic.index_splitter.models import IndexSplitter
from toolkit.elastic.validators import (
    check_for_banned_beginning_chars,
    check_for_colons,
    check_for_special_symbols,
    check_for_upper_case,
    check_for_wildcards
)
from toolkit.serializer_constants import CommonModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer


class IndexSplitterSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, CommonModelSerializerMixin, IndicesSerializerMixin, ProjectResourceUrlSerializer):
    url = serializers.SerializerMethodField()
    scroll_size = serializers.IntegerField(min_value=0, max_value=10000, required=False)
    query = serializers.JSONField(help_text='Query used to filter the indices. Defaults to an empty query.', required=False)
    train_index = serializers.CharField(help_text='Name of the train index.', allow_blank=False, required=True,
                                        validators=[
                                            check_for_wildcards,
                                            check_for_colons,
                                            check_for_special_symbols,
                                            check_for_banned_beginning_chars,
                                            check_for_upper_case
                                        ])
    test_index = serializers.CharField(help_text='Name of the test index.', allow_blank=False, required=True,
                                       validators=[
                                           check_for_wildcards,
                                           check_for_colons,
                                           check_for_special_symbols,
                                           check_for_banned_beginning_chars,
                                           check_for_upper_case
                                       ])
    fields = serializers.ListField(
        child=serializers.CharField(),
        help_text=f'Empty fields chooses all posted indices fields.',
        required=False
    )
    test_size = serializers.IntegerField(
        help_text='Size of the test set. Represents a percentage with "random" or "original" distribution and a quantity with "equal" or "custom" distribution.',
        required=False,
        min_value=1,
        max_value=10000
    )

    fact = serializers.CharField(required=False, help_text="Name of the fact on which the test index distribution will base.")
    str_val = serializers.CharField(required=False, help_text="Name of the fact value on which the test index distribution will base.")
    distribution = serializers.ChoiceField(choices=LABEL_DISTRIBUTION, default=LABEL_DISTRIBUTION[0][0], required=False, help_text='Distribution of the test set. Either "random", "original", "equal" or "custom".')
    custom_distribution = serializers.JSONField(default={}, help_text="A dictionary containing custom label distribution with keys as labels and values as quantities.")


    class Meta:
        model = IndexSplitter
        fields = ('id', 'url', 'author', 'description', 'indices', 'scroll_size', 'fields', 'query', 'train_index', 'test_index', "test_size", 'fact', 'str_val', 'distribution', 'custom_distribution', 'tasks')
        fields_to_parse = ('fields', 'custom_distribution')


    def validate_train_index(self, value):
        """ Check that new_index does not exist """
        open_indices, closed_indices = ElasticCore().get_indices()
        if value in open_indices or value in closed_indices:
            raise serializers.ValidationError(f"{value} already exists, choose a different name for your train index")
        return value


    def validate_test_index(self, value):
        """ Check that new_index does not exist """
        open_indices, closed_indices = ElasticCore().get_indices()
        if value in open_indices or value in closed_indices:
            raise serializers.ValidationError(f"{value} already exists, choose a different name for your test index")
        return value


    def validate_indices(self, value):
        """ check if index is in the relevant project indices field """
        project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        for index in value:
            if index.get("name") not in project_obj.get_indices():
                raise serializers.ValidationError(f'Index "{index.get("name")}" is not contained in your project indices "{project_obj.get_indices()}"')
        return value


    def validate_fields(self, value):
        ''' check if fields included in the request are in the relevant project fields '''
        project_fields = self._get_project_fields()
        field_data = [field["path"] for field in project_fields]
        for field in value:
            if field not in field_data:
                raise serializers.ValidationError(f'The fields you are attempting to add to new indices are not in current project fields: {project_fields}')
        return value


    def validate_query(self, value):
        val = json.loads(value)
        if "query" not in json.loads(value):
            raise serializers.ValidationError("Incorrect elastic query. Must contain field 'query'.")
        return value


    def validate(self, data):
        fact = data.get("fact")
        if data["distribution"] == "custom" and len(data["custom_distribution"]) == 0:
            raise serializers.ValidationError("field custom_distribution can not be empty with custom label distribution")
        if fact == "" and data["distribution"] in ["custom", "equal", "original"]:
            raise serializers.ValidationError('fact must be specified with "custom", "equal" or "original" distribution')
        if data["distribution"] in ["custom", "equal", "original"]:
            if "fields" in data and "texta_facts" not in data["fields"]:
                project_fields = self._get_project_fields()
                field_data = [field["path"] for field in project_fields]
                if "texta_facts" not in field_data:
                    raise serializers.ValidationError(f'Field texta_facts is required but it is not in project fields.: {project_fields}')
                else:
                    data["fields"].append("texta_facts")
        return data


    def _get_project_fields(self):
        project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        project_fields = ElasticCore().get_fields(indices=project_obj.get_indices())
        return project_fields
