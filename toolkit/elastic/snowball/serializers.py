from rest_framework import serializers

from ..choices import DEFAULT_SNOWBALL_LANGUAGE, get_snowball_choices


class SnowballSerializer(serializers.Serializer):
    text = serializers.CharField()
    language = serializers.ChoiceField(choices=get_snowball_choices(), default=DEFAULT_SNOWBALL_LANGUAGE)
