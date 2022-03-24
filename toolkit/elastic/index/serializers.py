from django.urls import reverse
from rest_framework import serializers
from toolkit.settings import DEFAULT_TEXTA_DATASOURCE_CHOICES

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
    description = serializers.CharField(max_length=255, default="", help_text="Description of index.")
    added_by = serializers.CharField(max_length=255, default="", help_text="Who added the index.")
    test = serializers.BooleanField(default=False, help_text="Is the index a test index.")
    source = serializers.CharField(max_length=255, default="", help_text="What is the source of this index.")
    client = serializers.CharField(max_length=255, default="", help_text="Who is the client related to this index.")
    domain = serializers.ChoiceField(choices=DEFAULT_TEXTA_DATASOURCE_CHOICES, default="")


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
        fields = ('id', 'is_open', 'url', 'name', 'description', 'added_by', 'test', 'source', 'client', 'domain', 'created_at')
        read_only_fields = ('id', 'url', 'created_at')


class IndexBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListSerializer(child=serializers.IntegerField(), default=[])


class IndexUpdateSerializer(serializers.ModelSerializer):
    is_open = serializers.BooleanField(default=True, read_only=True)
    name = serializers.CharField(
        read_only=True
    )
    description = serializers.CharField(max_length=255, default="", allow_blank=True, help_text="Description of index.")
    added_by = serializers.CharField(max_length=255, default="", allow_blank=True, help_text="Who added the index.")
    test = serializers.BooleanField(default=False, help_text="Is the index a test index.")
    source = serializers.CharField(max_length=255, default="", allow_blank=True, help_text="What is the source of this index.")
    client = serializers.CharField(max_length=255, default="", allow_blank=True, help_text="Who is the client related to this index.")
    domain = serializers.ChoiceField(choices=DEFAULT_TEXTA_DATASOURCE_CHOICES, default="")

    class Meta:
        model = Index
        fields = ('id', 'is_open', 'url', 'name', 'description', 'added_by', 'test', 'source', 'client', 'domain', 'created_at')
        read_only_fields = ('id', 'is_open', 'url', 'name', 'created_at')
