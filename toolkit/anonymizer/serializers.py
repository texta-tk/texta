from typing import List

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from toolkit.anonymizer import choices
from toolkit.anonymizer.models import Anonymizer
from toolkit.serializer_constants import FieldParseSerializer, ProjectResourceUrlSerializer


class AnonymizerSerializer(serializers.ModelSerializer, ProjectResourceUrlSerializer):
    description = serializers.CharField()

    replace_misspelled_names = serializers.BooleanField(
        default=choices.DEFAULT_REPLACE_MISSPELLED_NAMES, required=False,
        help_text=f'Replace incorrectly spelled occurrences of the name(s). NB! Can sometimes lead to falsely anonymizing semantically similar words! Default = {choices.DEFAULT_REPLACE_MISSPELLED_NAMES}.'
    )
    replace_single_last_names = serializers.BooleanField(
        default=choices.DEFAULT_REPLACE_SINGLE_LAST_NAMES,
        required=False,
        help_text=f'Replace last names occurring without first names. Default = {choices.DEFAULT_REPLACE_SINGLE_LAST_NAMES}.'
    )
    replace_single_first_names = serializers.BooleanField(
        default=choices.DEFAULT_REPLACE_SINGLE_FIRST_NAMES,
        required=False,
        help_text=f'Replace first names occurring without last names. Default = {choices.DEFAULT_REPLACE_SINGLE_FIRST_NAMES}.'
    )
    misspelling_threshold = serializers.FloatField(
        default=choices.DEFAULT_MISSPELLING_THRESHOLD,
        min_value=0.0,
        max_value=1.0,
        required=False,
        help_text=f'Minimum required Jaro-Winkler similarity of text matches and true names for anonymizing the matches. Used only if replace_misspelled_names=True. Default = {choices.DEFAULT_MISSPELLING_THRESHOLD}.'
    )
    mimic_casing = serializers.BooleanField(
        default=choices.DEFAULT_MIMIC_CASING,
        required=False,
        help_text=f'Anonymize name(s) in different cases. Default = {choices.DEFAULT_MIMIC_CASING}.'
    )
    auto_adjust_threshold = serializers.BooleanField(
        default=choices.DEFAULT_AUTO_ADJUST,
        required=False,
        help_text=f'Automatically adjust misspelling threshold for avoiding errors with anonymizing very similar names. NB! Automatically adjusted threshold is always >= misspelling_threshold before adjustment. Default = {choices.DEFAULT_AUTO_ADJUST}.'
    )

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
    consistent_replacement = serializers.BooleanField(default=choices.DEFAULT_CONSISTENT_REPLACEMENT, required=False, help_text=f'Replace name X in different texts with the same replacement string. Default = {choices.DEFAULT_CONSISTENT_REPLACEMENT}.')


    def validate_names(self, value: List[str]):
        error_message = "Value '{}' should be in format ['last_name, first_name']! Are you missing a comma?"
        for name in value:
            if "," not in name:
                raise ValidationError(error_message.format(name))
        return value
