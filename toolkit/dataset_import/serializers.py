from rest_framework import serializers

from toolkit.serializer_constants import CommonModelSerializerMixin, FieldParseSerializer, ProjectResourceUrlSerializer
from .models import DatasetImport
from ..elastic.validators import check_for_banned_beginning_chars, check_for_colons, check_for_special_symbols, check_for_upper_case, check_for_wildcards


class DatasetImportSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, CommonModelSerializerMixin, ProjectResourceUrlSerializer):
    file = serializers.FileField(help_text='File to upload.', write_only=True)
    separator = serializers.CharField(help_text='Separator (CSV only).', required=False)
    index = serializers.CharField(
        help_text='Name of the Elasticsearch index to upload the documents into. Must be all lowercase and only consist of alphabetical and numerical values.',
        validators=[
            check_for_upper_case,
            check_for_banned_beginning_chars,
            check_for_special_symbols,
            check_for_colons,
            check_for_wildcards
        ]
    )
    url = serializers.SerializerMethodField()


    class Meta:
        model = DatasetImport
        fields = ('id', 'url', 'author', 'description', 'index', 'separator', 'num_documents', 'num_documents_success', 'file', 'tasks')
        fields_to_parse = ()
        read_only_fields = ('id', 'author', 'num_documents', 'num_documents_success', 'tasks')
