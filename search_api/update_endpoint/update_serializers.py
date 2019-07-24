from rest_framework import serializers
from search_api.validator_serializers.common_validators import validate_auth_token


class UpdateItem(serializers.Serializer):
    id = serializers.CharField(required=True, allow_blank=False, min_length=0)
    index = serializers.CharField(required=True, allow_blank=False, min_length=0)
    doc_type = serializers.CharField(required=False, allow_blank=False, min_length=0)
    changes = serializers.DictField(required=True)


class UpdateRequestSerializer(serializers.Serializer):
    auth_token = serializers.CharField(validators=[validate_auth_token], required=True, min_length=0, allow_blank=False)
    items = serializers.ListField(child=UpdateItem(), required=True, allow_empty=False)
