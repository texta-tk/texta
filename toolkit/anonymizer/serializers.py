from typing import List

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer
from .models import Anonymizer

class AnonymizerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()

    replace_misspelled_names = serializers.BooleanField(default=True, required=False, help_text='Replace incorrectly spelled occurrences of the name(s). NB! Can sometimes lead to falsely anonymizing semantically similar words! Default: True')
    replace_single_last_names = serializers.BooleanField(default=True, required=False, help_text='Replace last names occurring without first names. Default: True')
    replace_single_first_names = serializers.BooleanField(default=True, required=False, help_text='Replace first names occurring without last names. Default: True')
    misspelling_threshold = serializers.FloatField(default=0.9, min_value=0.0, max_value=1.0, required=False, help_text='Minimum required Jaro-Winkler similarity of text matches and true names for anonymizing the matches. Used only if replace_misspelled_names=True. Default=0.9')
    mimic_casing = serializers.BooleanField(default=True, required=False, help_text='Anonymize name(s) in different cases. Default=True')
    auto_adjust_threshold = serializers.BooleanField(default=False, required=False,
                                                     help_text='Automatically adjust misspelling threshold for avoiding errors with anonymizing very similar names. NB! Automatically adjusted threshold is always >= misspelling_threshold before adjustment. Default=False')

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
                  'mimic_casing',
                  'auto_adjust_threshold')


class AnonymizerAnonymizeTextSerializer(FieldParseSerializer, serializers.Serializer):
    text = serializers.CharField(required=True, help_text='Text to anonymize')
    names = serializers.ListField(help_text='List of names to anonymize in form ["last_name, first_name"]', child=serializers.CharField(required=True))


    def validate_names(self, value: List[str]):
        error_message = "Value '{}' should be in format ['last_name, first_name']! Are you missing a comma?"
        for name in value:
            if "," not in name:
                raise ValidationError(error_message.format(name))
        return value


class AnonymizerAnonymizeTextsSerializer(FieldParseSerializer, serializers.Serializer):
    texts = serializers.ListField(child=serializers.CharField(required=True), help_text='Texts to anonymize.')
    names = serializers.ListField(help_text='List of names to anonymize in form ["last_name, first_name"]',
                                  child=serializers.CharField(required=True))
    consistent_replacement = serializers.BooleanField(default=True, required=False, help_text='Replace name X in different texts with the same replacement string.')

    def validate_names(self, value: List[str]):
        error_message = "Value '{}' should be in format ['last_name, first_name']! Are you missing a comma?"
        for name in value:
            if "," not in name:
                raise ValidationError(error_message.format(name))
        return value
