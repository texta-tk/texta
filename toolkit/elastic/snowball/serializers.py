from rest_framework import serializers
from ..choices import get_snowball_choices


class SnowballSerializer(serializers.Serializer):
    text = serializers.CharField()
    language = serializers.ChoiceField(choices=get_snowball_choices(), default=None)

