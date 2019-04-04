from rest_framework import serializers

from account.models import Profile


def validate_auth_token(auth_token: str):
    authenticated_token = Profile.objects.filter(auth_token=auth_token).first()
    if not authenticated_token:
        raise serializers.ValidationError('Failed to authenticate token.')


class LikeThisItem(serializers.Serializer):
    dataset_id = serializers.IntegerField(required=True, min_value=0)
    document_id = serializers.CharField(required=True, min_length=0)


class ValidateFormSerializer(serializers.Serializer):
    auth_token = serializers.CharField(required=True, validators=[validate_auth_token], min_length=0, allow_blank=False)
    like = serializers.ListField(required=True, child=LikeThisItem(), allow_empty=False)
    fields = serializers.ListField(child=serializers.CharField(min_length=0), required=True, allow_empty=False)
    size = serializers.IntegerField(default=10, required=False, max_value=10000)
    returned_fields = serializers.ListField(required=False, child=serializers.CharField(min_length=0))
