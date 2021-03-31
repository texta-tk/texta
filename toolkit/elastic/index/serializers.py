from django.urls import reverse
from rest_framework import serializers

from toolkit.elastic.index.models import Index
from toolkit.elastic.validators import (
    check_for_banned_beginning_chars,
    check_for_colons,
    check_for_special_symbols,
    check_for_upper_case,
    check_for_wildcards
)
from toolkit.settings import REST_FRAMEWORK


class AddMappingToIndexSerializer(serializers.Serializer):
    mappings = serializers.DictField()


# An empty serializer because otherwise it defaults to the Index one, creating confusion
# inside the BrowsableAPI.
class AddTextaFactsMapping(serializers.Serializer):
    pass


class IndexSerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(default=True)
    url = serializers.SerializerMethodField()
    name = serializers.CharField(
        max_length=255,
        validators=[
            check_for_wildcards,
            check_for_colons,
            check_for_special_symbols,
            check_for_banned_beginning_chars,
            check_for_upper_case
        ]
    )


    def get_url(self, obj):
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")

        index = reverse(f"{default_version}:index-detail", kwargs={"pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    class Meta:
        model = Index
        fields = "__all__"


class IndexBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListSerializer(child=serializers.IntegerField(), default=[])
