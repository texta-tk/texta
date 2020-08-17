from rest_framework import serializers

from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from .models import Anonymizer

class AnonymizerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()

    replace_misspelled_names = serializers.BooleanField(default=True, required=False)
    replace_single_last_names = serializers.BooleanField(default=True, required=False)
    replace_single_first_names = serializers.BooleanField(default=True, required=False)
    misspelling_threshold = serializers.FloatField(default=0.9, min_value=0.0, max_value=1.0, required=False)
    mimic_casing = serializers.BooleanField(default=True, required=False)

    url = serializers.SerializerMethodField()

    class Meta:
        model = Anonymizer
        fields = ('id',
                  'url',
                  'description',
                  'replace_misspelled_names',
                  'replace_single_last_names',
                  'replace_single_first_names',
                  'misspelling_threshold',
                  'mimic_casing')


class AnonymizerAnonymizeTextSerializer(FieldParseSerializer, serializers.Serializer):
    text = serializers.CharField(required=True)
    names = serializers.ListField(help_text='List of names to anonymize in form ["last_name, first_name"]',
                                  child=serializers.CharField(required=True))


class AnonymizerAnonymizeTextsSerializer(FieldParseSerializer, serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True))
    names = serializers.ListField(help_text='List of names to anonymize in form ["last_name, first_name"]',
                                  child=serializers.CharField(required=True))
