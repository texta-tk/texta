import logging

from elasticsearch_dsl import Q
from rest_framework import serializers

from account.models import Profile
from texta.settings import ERROR_LOGGER


def validate_auth_token(auth_token: str):
    authenticated_token = Profile.objects.filter(auth_token=auth_token).first()
    if not authenticated_token:
        raise serializers.ValidationError('Failed to authenticate token.')


# To make sure the user is notified for when they try to use an agg that does not exist.
def validate_agg_name(agg_type: str):
    valid_types = ["percentiles", "avg", "value_count", "extended_stats", "min", "max", "stats", "sum", "composite", "terms"]
    if agg_type not in valid_types:
        raise serializers.ValidationError("Currently only the following aggregations are supported: {}".format(valid_types))


# Tries to parse the inserted filter query, when it fails they did something wrong.
def validate_filter(filter: dict):
    try:
        query = Q(filter)
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception("Could not parse filter query {}.".format(filter))
        raise serializers.ValidationError("Could not parse the filter, query. Make sure you have not included the top 'query' key!")


class LikeThisItem(serializers.Serializer):
    dataset_id = serializers.IntegerField(required=True, min_value=0)
    document_id = serializers.CharField(required=True, min_length=0)


class AggregationsItem(serializers.Serializer):
    bucket_name = serializers.CharField(required=True)
    agg_type = serializers.CharField(required=True, validators=[validate_agg_name])
    field = serializers.CharField(required=False)
    sources = serializers.ListField(required=False)
    size = serializers.IntegerField(required=False, min_value=0, max_value=10001)
    after_key = serializers.DictField(required=False)



class ValidateFormSerializer(serializers.Serializer):
    auth_token = serializers.CharField(required=True, validators=[validate_auth_token], min_length=0, allow_blank=False)
    like = serializers.ListField(required=True, child=LikeThisItem(), allow_empty=False)
    fields = serializers.ListField(child=serializers.CharField(min_length=0), required=True, allow_empty=False)
    size = serializers.IntegerField(default=10, required=False, max_value=10000)
    returned_fields = serializers.ListField(required=False, child=serializers.CharField(min_length=0))
    filters = serializers.ListField(required=False, child=serializers.DictField(validators=[validate_filter]))
    aggregations = serializers.ListField(required=False, child=AggregationsItem())
    if_agg_only = serializers.BooleanField(default=False)
