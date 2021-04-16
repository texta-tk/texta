from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from ..choices import get_snowball_choices


class SnowballSerializer(serializers.Serializer):
    text = serializers.CharField()
    language = serializers.CharField(default=None)


    def validate_language(self, value: str):
        languages = get_snowball_choices()
        if value not in languages:
            raise ValidationError(f"Language '{value}' is not amongst the supported languages: {languages}!")
        return value
