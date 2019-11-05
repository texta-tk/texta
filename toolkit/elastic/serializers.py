from rest_framework import serializers

from toolkit.elastic.core import ElasticCore


class SpamSerializer(serializers.Serializer):
    target_field = serializers.CharField(required=True)
    from_date = serializers.CharField(default="now-1h")
    to_date = serializers.CharField(default="now")
    date_field = serializers.CharField(required=True)
    aggregation_size = serializers.IntegerField(min_value=1, max_value=10000, default=10)
    min_doc_count = serializers.IntegerField(min_value=1, default=10)
    common_feature_fields = serializers.MultipleChoiceField(choices=[])


    def __init__(self, *args, **kwargs):
        super(SpamSerializer, self).__init__(*args, **kwargs)
        common_feature_fields_choices = [field["path"] for field in ElasticCore().get_fields()]
        self.fields['common_feature_fields'].choices = sorted(common_feature_fields_choices)
