from rest_framework import serializers
from toolkit.elastic.validators import (
    check_for_banned_beginning_chars,
    check_for_colons,
    check_for_special_symbols,
    check_for_upper_case,
    check_for_wildcards
)


class AddFaceSerializer(serializers.Serializer):
    image = serializers.FileField()
    index = serializers.CharField(validators=[
        check_for_wildcards,
        check_for_colons,
        check_for_special_symbols,
        check_for_banned_beginning_chars,
        check_for_upper_case
        ]
    )
    name = serializers.CharField(required=False, default="KNOWN_FACE")
    value = serializers.CharField(required=False, default="John Not Doe")


class FaceAnalyzerSerializer(serializers.Serializer):
    image = serializers.FileField()
    store_image = serializers.BooleanField(default=False)
    index = serializers.CharField(required=False, validators=[
        check_for_wildcards,
        check_for_colons,
        check_for_special_symbols,
        check_for_banned_beginning_chars,
        check_for_upper_case
        ]
    )
    score = serializers.FloatField(max_value=0.9, min_value=0.1, default=0.93, required=False)
