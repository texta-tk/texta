from rest_framework import serializers
import json
import re

from .models import DatasetImport
from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import ProjectResourceUrlSerializer, FieldParseSerializer

class DatasetImportSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    file = serializers.FileField(help_text='File to upload.', write_only=True)
    separator = serializers.CharField(help_text='Separator (CSV only).', required=False)
    index = serializers.CharField(help_text='Index to upload dataset into.')
    task = TaskSerializer(read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = DatasetImport
        fields = ('id', 'url', 'author_username', 'description', 'index', 'separator', 'num_documents', 'num_documents_success', 'file', 'task')
        fields_to_parse = ()
        read_only_fields = ('id', 'author_username', 'num_documents', 'num_documents_success', 'task')
