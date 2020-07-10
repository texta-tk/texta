from rest_framework import serializers

from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from .models import Anonymizer

class AnonymizerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()

    allow_fuzzy_matching = serializers.BooleanField(default=True, required=False)
    extract_single_last_names = serializers.BooleanField(default=True, required=False)
    extract_single_first_names = serializers.BooleanField(default=True, required=False)
    fuzzy_threshold = serializers.FloatField(default=0.9, required=False)
    mimic_casing = serializers.BooleanField(default=True, required=False)

    url = serializers.SerializerMethodField()

    class Meta:
        model = Anonymizer
        fields = ('id',
                  'url',
                  'description',
                  'allow_fuzzy_matching',
                  'extract_single_last_names',
                  'extract_single_first_names',
                  'fuzzy_threshold',
                  'mimic_casing')


class AnonymizerAnonymizeTextSerializer(FieldParseSerializer, serializers.Serializer):
    text = serializers.CharField(required=True)
    names = serializers.ListField(help_text='List of names to anonymize in form ["last_name, first_name"]',
                                  child=serializers.CharField(required=True))


class AnonymizerAnonymizeTextsSerializer(FieldParseSerializer, serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True))
    names = serializers.ListField(help_text='List of names to anonymize in form ["last_name, first_name"]',
                                  child=serializers.CharField(required=True))
