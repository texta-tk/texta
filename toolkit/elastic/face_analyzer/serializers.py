from rest_framework import serializers
from toolkit.elastic.validators import (
    check_for_banned_beginning_chars,
    check_for_colons,
    check_for_special_symbols,
    check_for_upper_case,
    check_for_wildcards
)


class AddFaceSerializer(serializers.Serializer):
    image = serializers.FileField(help_text="Image with faces to be analyzed and indexed in Elasticsearch.")
    index = serializers.CharField(
        help_text="Elasticsearch index used for indexing found faces.",
        validators=[
            check_for_wildcards,
            check_for_colons,
            check_for_special_symbols,
            check_for_banned_beginning_chars,
            check_for_upper_case
        ]
    )
    name = serializers.CharField(
        required=False,
        default="KNOWN_FACE",
        help_text="Name for the facial fact added to Elasticsearch."
    )
    value = serializers.CharField(
        required=False,
        default="John Not Doe",
        help_text="Value for the facial fact added to Elasticsearch."
    )


class FaceAnalyzerSerializer(serializers.Serializer):
    image = serializers.FileField(help_text="Image to be analyzed for faces.")
    store_image = serializers.BooleanField(default=False, help_text="Store image in TK for later use.")
    index = serializers.CharField(required=False,
        help_text="Elasticsearch index used for face comparison.",
        validators=[
            check_for_wildcards,
            check_for_colons,
            check_for_special_symbols,
            check_for_banned_beginning_chars,
            check_for_upper_case
        ]
    )
    score = serializers.FloatField(
        max_value=0.9,
        min_value=0.1,
        default=0.93,
        required=False,
        help_text="Score threshold for face comparison."
    )
