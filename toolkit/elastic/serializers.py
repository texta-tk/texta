from rest_framework import serializers


class SpamSerializer(serializers.Serializer):
    target_field = serializers.CharField(required=True)
    from_date = serializers.CharField(default="now-1h")
    to_date = serializers.CharField(default="now")
    date_field = serializers.CharField(required=True)
    aggregation_size = serializers.IntegerField(min_value=1, max_value=10000, default=10)
    min_doc_count = serializers.IntegerField(min_value=1, default=10)
    common_feature_fields = serializers.ListField(default=[], min_length=1, child=serializers.CharField())
