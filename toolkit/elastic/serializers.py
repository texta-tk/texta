from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from toolkit.core.project.models import Project
from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.models import Index, Reindexer
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.elastic.validators import check_for_banned_beginning_chars, check_for_colons, check_for_special_symbols, check_for_upper_case, check_for_wildcards
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer


class ElasticScrollSerializer(serializers.Serializer):
    indices = serializers.ListField(child=serializers.CharField(), default=[], help_text="From which indices to search, by default all project indices are chosen.")
    scroll_id = serializers.CharField(required=False)
    query = serializers.DictField(default=EMPTY_QUERY, help_text="Query to limit returned documents.")
    documents_size = serializers.IntegerField(min_value=1, max_value=300, default=300, help_text="How many documents should be returned in the response. Max is 300.")
    fields = serializers.ListField(default=["*"], help_text="List of field names you wish to be return by Elasticsearch.")
    with_meta = serializers.BooleanField(default=False, help_text="Whether to return raw Elasticsearch hits or remove the metadata from the documents.")


    # Change what is returned to serializer_instance.validated_data
    def to_internal_value(self, data):
        values = super(ElasticScrollSerializer, self).to_internal_value(data)
        if "query" in values:
            query_field = values.get("query", None)
            if query_field:
                values["query"] = {"query": query_field["query"]}  # Make sure we only keep the query, without aggregations.
            else:
                raise ValidationError("Query must have an 'query' key to conduct a search.")
        return values


class IndexSerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(default=True)
    url = serializers.SerializerMethodField()
    name = serializers.CharField(
        max_length=255,
        validators=[
            check_for_wildcards,
            check_for_colons,
            check_for_special_symbols,
            check_for_banned_beginning_chars,
            check_for_upper_case
        ]
    )

    def get_url(self, obj):
        index = reverse("v1:index-detail", kwargs={"pk": obj.pk})
        request = self.context["request"]
        url = request.build_absolute_uri(index)
        return url

    class Meta:
        model = Index
        fields = "__all__"


class ReindexerCreateSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    url = serializers.SerializerMethodField()
    description = serializers.CharField(help_text='Describe your re-indexing task', required=True, allow_blank=False)
    indices = serializers.ListField(child=serializers.CharField(), help_text=f'Add the indices, you wish to reindex into a new index.', write_only=True, required=True)
    fields = serializers.ListField(child=serializers.CharField(),
                                   help_text=f'Empty fields chooses all posted indices fields. Fields content adds custom field content to the new index.',
                                   required=False)
    query = serializers.JSONField(help_text='Add a query, if you wish to filter the new reindexed index.', required=False)
    new_index = serializers.CharField(help_text='Your new re-indexed index name', allow_blank=False, required=True)
    random_size = serializers.IntegerField(help_text='Picks a subset of documents of chosen size at random. Disabled by default.',
                                           required=False)
    field_type = serializers.ListField(help_text=f'Used to update the fieldname and the field type of chosen paths.',
                                       required=False)
    task = TaskSerializer(read_only=True)


    class Meta:
        model = Reindexer
        fields = ('id', 'url', 'author_username', 'description', 'indices', 'fields', 'query', 'new_index', 'random_size', 'field_type', 'task')
        fields_to_parse = ('fields', 'field_type')


    def validate_new_index(self, value):
        """ Check that new_index does not exist """
        if value in ElasticCore().get_indices():
            raise serializers.ValidationError("new_index already exists, choose a different name for your reindexed index")
        return value


    def validate_indices(self, value):
        """ check if re-indexed index is in the relevant project indices field """
        project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        for index in value:
            if index not in project_obj.get_indices():
                raise serializers.ValidationError(f'Index "{index}" is not contained in your project indices "{repr(project_obj.indices)}"')
        return value


    def validate_fields(self, value):
        ''' check if changed fields included in the request are in the relevant project fields '''
        project_obj = Project.objects.get(id=self.context['view'].kwargs['project_pk'])
        project_fields = ElasticCore().get_fields(indices=project_obj.get_indices())
        field_data = [field["path"] for field in project_fields]
        for field in value:
            if field not in field_data:
                raise serializers.ValidationError(f'The fields you are attempting to re-index are not in current project fields: {project_fields}')
        return value
