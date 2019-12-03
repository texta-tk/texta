from rest_framework import serializers
import json
import re

from .models import DatasetImport
from toolkit.core.task.serializers import TaskSerializer
from toolkit.serializer_constants import ProjectResourceUrlSerializer, FieldParseSerializer

class DatasetImportSerializer(FieldParseSerializer, serializers.HyperlinkedModelSerializer, ProjectResourceUrlSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    file = serializers.FileField(help_text='File to upload.', write_only=True)
    index = serializers.CharField(help_text='Index to upload dataset into.')
    task = TaskSerializer(read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = DatasetImport
        fields = ('id', 'url', 'author_username', 'description', 'index', 'num_documents', 'file', 'task')
        fields_to_parse = ()
        read_only_fields = ('id', 'author_username', 'num_documents', 'task')
