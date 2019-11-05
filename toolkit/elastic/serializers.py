from rest_framework import serializers


class SpamSerializer(serializers.Serializer):
    target_field = serializers.CharField(required=True, help_text="Name of the Elasticsearch field you want to use for analysis.")
    from_date = serializers.CharField(default="now-1h", help_text="Lower threshold for limiting the date range. Accepts timestamps and Elasticsearch date math.")
    to_date = serializers.CharField(default="now", help_text="Upper threshold for limiting the date range. Accepts timestamps and Elasticsearch date math.")
    date_field = serializers.CharField(required=True, help_text="Name of the Elasticsearch field you want to use to limit the date range.")
    aggregation_size = serializers.IntegerField(min_value=1, max_value=10000, default=10, help_text="Number of how many items should be returned per aggregation.")
    min_doc_count = serializers.IntegerField(min_value=1, default=10, help_text="Number to set the minimum document matches that are returned.")
    common_feature_fields = serializers.ListField(child=serializers.CharField(), help_text="Elasticsearch field names to match common patterns.")
