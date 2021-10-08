import json
from rest_framework import serializers
from texta_crf_extractor.feature_extraction import DEFAULT_LAYERS, DEFAULT_EXTRACTORS
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY
from toolkit.serializer_constants import (
    FieldParseSerializer,
    IndicesSerializerMixin,
    ElasticScrollMixIn,
    ProjectResourceUrlSerializer,
    ProjectFilteredPrimaryKeyRelatedField,
    QUERY_HELPTEXT,
    DESCRIPTION_HELPTEXT
)
from toolkit.embedding.models import Embedding
from .models import CRFExtractor
from .choices import FEATURE_FIELDS_CHOICES, FEATURE_EXTRACTOR_CHOICES


class CRFExtractorSerializer(serializers.ModelSerializer, IndicesSerializerMixin, ProjectResourceUrlSerializer):
    description = serializers.CharField(help_text=DESCRIPTION_HELPTEXT)
    author = UserSerializer(read_only=True)
    query = serializers.JSONField(
        help_text=QUERY_HELPTEXT,
        default=EMPTY_QUERY,
    )

    mlp_field = serializers.CharField(help_text='MLP field used to build the model.')
    labels = serializers.JSONField(
        default=["GPE", "ORG", "PER", "LOC"],
        help_text="List of labels used to train the extraction model."
    )
    num_iter = serializers.IntegerField(
        default=100,
        help_text="Number of iterations used in training."
    )
    test_size = serializers.FloatField(
        default=0.3,
        help_text="Proportion of documents reserved for testing the model."
    )
    c1 = serializers.FloatField(default=1.0, help_text="Coefficient for L1 penalty.")
    c2 = serializers.FloatField(default=1.0, help_text="Coefficient for L2 penalty.")
    bias = serializers.BooleanField(
        default=True,
        help_text="Capture the proportion of a given label in the training set."
    )
    window_size = serializers.IntegerField(
        default=2,
        help_text="Number of words before and after the observed word analyzed.",
        )
    suffix_len = serializers.CharField(
        default=json.dumps((2,2)),
        help_text="Number of characters (min, max) used for word suffixes as features."
        )
    feature_fields = serializers.MultipleChoiceField(
        choices=FEATURE_FIELDS_CHOICES,
        default=DEFAULT_LAYERS,
        help_text="Layers (MLP subfields) used as features for the observed word."
    )
    context_feature_fields = serializers.MultipleChoiceField(
        choices=FEATURE_FIELDS_CHOICES,
        default=DEFAULT_LAYERS,
        help_text="Layers (MLP subfields) used as features for the context of the observed word."
    )
    feature_extractors = serializers.MultipleChoiceField(
        choices=FEATURE_EXTRACTOR_CHOICES,
        default=DEFAULT_EXTRACTORS,
        help_text="Feature extractors used for the observed word and it's context."
    )
    embedding = ProjectFilteredPrimaryKeyRelatedField(
        queryset=Embedding.objects,
        many=False,
        read_only=False,
        allow_null=True,
        default=None,
        help_text="Embedding to use for finding similar words for the observed word and it's context."
    )
    url = serializers.SerializerMethodField()


    class Meta:
        model = CRFExtractor
        fields = (
            'id', 'url', 'author', 'description', 'query', 'indices', 'mlp_field',
            'window_size', 'test_size', 'num_iter', 'c1', 'c2', 'bias', 'suffix_len',
            'labels', 'feature_fields', 'context_feature_fields', 'feature_extractors',
            'embedding'
        )
        read_only_fields = ()
        fields_to_parse = ('fields',)


class ApplyCRFExtractorSerializer(FieldParseSerializer, IndicesSerializerMixin, ElasticScrollMixIn):
    mlp_fields = serializers.ListField(child=serializers.CharField())
    query = serializers.JSONField(
        help_text='Filter the documents which to scroll and apply to.',
        default=EMPTY_QUERY
    )


class CRFExtractorTagTextSerializer(serializers.Serializer):
    text = serializers.CharField(help_text="Use the CRF model on text.")
