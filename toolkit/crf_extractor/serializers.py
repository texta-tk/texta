import json

from rest_framework import serializers
from texta_crf_extractor.feature_extraction import DEFAULT_EXTRACTORS, DEFAULT_LAYERS
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.embedding.models import Embedding
from toolkit.serializer_constants import (CommonModelSerializerMixin, ElasticScrollMixIn, FavoriteModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin, ProjectFilteredPrimaryKeyRelatedField, ProjectResourceUrlSerializer, QUERY_HELPTEXT)
from .choices import FEATURE_EXTRACTOR_CHOICES, FEATURE_FIELDS_CHOICES
from .models import CRFExtractor


class CRFExtractorSerializer(FieldParseSerializer, serializers.ModelSerializer, CommonModelSerializerMixin, FavoriteModelSerializerMixin, IndicesSerializerMixin, ProjectResourceUrlSerializer):
    query = serializers.JSONField(
        help_text=QUERY_HELPTEXT,
        default=json.dumps(EMPTY_QUERY, ensure_ascii=False),
        required=False
    )

    mlp_field = serializers.CharField(help_text='MLP field used to build the model.')

    labels = serializers.JSONField(
        default=["GPE", "ORG", "PER", "LOC"],
        help_text="List of labels used to train the extraction model."
    )

    c_values = serializers.JSONField(
        default=[0.001, 0.1, 0.5],
        help_text="List of C-values to test during training. Best will be used."
    )

    num_iter = serializers.IntegerField(
        default=100,
        help_text="Number of iterations used in training."
    )
    test_size = serializers.FloatField(
        default=0.3,
        help_text="Proportion of documents reserved for testing the model."
    )

    bias = serializers.BooleanField(
        default=True,
        help_text="Capture the proportion of a given label in the training set."
    )
    window_size = serializers.IntegerField(
        default=2,
        help_text="Number of words before and after the observed word analyzed.",
    )
    suffix_len = serializers.JSONField(
        default=json.dumps((2, 2)),
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
    context_feature_extractors = serializers.MultipleChoiceField(
        choices=FEATURE_EXTRACTOR_CHOICES,
        default=DEFAULT_EXTRACTORS,
        help_text="Feature extractors used for the context of the observed word."
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
            'window_size', 'test_size', 'num_iter', 'best_c1', 'best_c2', 'bias', 'suffix_len',
            'labels', 'feature_fields', 'context_feature_fields', 'feature_extractors', 'context_feature_extractors',
            'embedding', 'tasks', 'precision', 'recall', 'f1_score', 'c_values', 'is_favorited',
        )
        read_only_fields = ('precision', 'tasks', 'recall', 'f1_score', 'best_c1', 'best_c2')
        fields_to_parse = ('labels', 'suffix_len', 'c_values')


class ApplyCRFExtractorSerializer(FieldParseSerializer, IndicesSerializerMixin, ElasticScrollMixIn):
    mlp_fields = serializers.ListField(child=serializers.CharField())
    query = serializers.JSONField(
        help_text="Filter the documents which to scroll and apply to.",
        default=json.dumps(EMPTY_QUERY)
    )
    label_suffix = serializers.CharField(
        help_text="Suffix added to fact names to distinguish them from other facts with the same name.",
        default=""
    )


class CRFExtractorTagTextSerializer(serializers.Serializer):
    text = serializers.CharField(help_text="Use the CRF model on text.")
