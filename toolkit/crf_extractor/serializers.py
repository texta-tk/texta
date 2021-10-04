import json
from rest_framework import serializers, fields
from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.serializer_constants import (
    FieldParseSerializer,
    IndicesSerializerMixin,
    ProjectResourceUrlSerializer
)
from toolkit.multiselectfield import PatchedMultiSelectField

from toolkit.embedding.models import Embedding
from .models import CRFExtractor
from .choices import FEATURE_FIELDS_CHOICES, FEATURE_EXTRACTOR_CHOICES


class CRFExtractorSerializer(serializers.ModelSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer):
    author = UserSerializer(read_only=True)
    description = serializers.CharField(help_text=f'Description for the CRFExtractor model.')

    field = serializers.CharField(help_text=f'Text field used to build the model.')

    labels = serializers.JSONField(default=["GPE", "ORG", "PER", "LOC"])

    num_iter = serializers.IntegerField(default=100)
    test_size = serializers.FloatField(default=0.3)
    c1 = serializers.FloatField(default=1.0)
    c2 = serializers.FloatField(default=1.0)
    bias = serializers.BooleanField(default=True)
    window_size = serializers.IntegerField(default=2)
    suffix_len = serializers.CharField(default=json.dumps((2,2)))

    feature_fields = fields.MultipleChoiceField(choices=FEATURE_FIELDS_CHOICES, default=FEATURE_FIELDS_CHOICES)
    context_feature_fields = fields.MultipleChoiceField(choices=FEATURE_FIELDS_CHOICES, default=FEATURE_FIELDS_CHOICES)
    feature_extractors = fields.MultipleChoiceField(choices=FEATURE_EXTRACTOR_CHOICES, default=FEATURE_EXTRACTOR_CHOICES)

    window_size = serializers.IntegerField(default=2)
    url = serializers.SerializerMethodField()


    class Meta:
        model = CRFExtractor
        fields = (
            'id', 'url', 'author', 'description', 'query', 'indices', 'field', 'window_size', 'test_size',
            'num_iter', 'c1', 'c2', 'bias', 'suffix_len', 'labels', 'feature_fields', 'context_feature_fields',
            'feature_extractors'
        )
        read_only_fields = ()
        fields_to_parse = ('fields',)


class CRFExtractorTagTextSerializer(serializers.Serializer):
    text = serializers.CharField()
