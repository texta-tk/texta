import json
from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.serializer_constants import (
    FieldParseSerializer,
    IndicesSerializerMixin,
    ProjectResourceUrlSerializer
)

from toolkit.embedding.models import Embedding
from .models import CRFExtractor


class CRFExtractorSerializer(serializers.ModelSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer):
    author = UserSerializer(read_only=True)
    description = serializers.CharField(help_text=f'Description for the CRFExtractor model.')

    field = serializers.CharField(help_text=f'Text field used to build the model.')

    # add other params

    window_size = serializers.IntegerField(default=2)
    url = serializers.SerializerMethodField()



    class Meta:
        model = CRFExtractor
        fields = (
            'id', 'url', 'author', 'description', 'query', 'indices', 'field', 'window_size',
        )
        read_only_fields = ()
        fields_to_parse = ('fields',)
