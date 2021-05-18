import json

from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ApplyStemmerWorker
from ..choices import DEFAULT_SNOWBALL_LANGUAGE, get_snowball_choices
from ..index.serializers import IndexSerializer
from ..tools.searcher import EMPTY_QUERY
from ...core.task.serializers import TaskSerializer
from ...serializer_constants import FieldValidationSerializer


class SnowballSerializer(serializers.Serializer):
    text = serializers.CharField()
    language = serializers.ChoiceField(choices=get_snowball_choices(), default=DEFAULT_SNOWBALL_LANGUAGE)


class ApplySnowballSerializer(serializers.ModelSerializer, FieldValidationSerializer):
    description = serializers.CharField()
    indices = IndexSerializer(many=True, default=[])
    author_username = serializers.CharField(source='author.username', read_only=True, required=False)
    task = TaskSerializer(read_only=True, required=False)
    url = serializers.SerializerMethodField()
    query = serializers.JSONField(help_text='Query in JSON format', default=json.dumps(EMPTY_QUERY))
    stemmer_lang = serializers.ChoiceField(choices=get_snowball_choices(), default=DEFAULT_SNOWBALL_LANGUAGE, help_text="Which language stemmer to apply on the text.")
    fields = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=False, help_text="Which field to stem.")
    detect_lang = serializers.BooleanField(help_text="Whether to detect the language for the stemming on the fly.", default=False)
    es_timeout = serializers.IntegerField(min_value=1, max_value=60, default=25, help_text="How many minutes should there be between scroll requests before triggering a timeout.")
    bulk_size = serializers.IntegerField(min_value=1, max_value=500, default=100, help_text="How many documents should be returned by Elasticsearch with each request.")


    def validate(self, attrs):
        stemmer_lang_exists = "stemmer_lang" in attrs and attrs["stemmer_lang"]
        detect_lang_exists = "detect_lang" in attrs and attrs["detect_lang"]
        if stemmer_lang_exists and detect_lang_exists:
            raise ValidationError("Fields 'stemmer_lang' and 'detect_lang' are mutually exclusive, please choose one!")

        if not stemmer_lang_exists and not detect_lang_exists:
            raise ValidationError("Please choose at least one of the fields 'stemmer_lang' or 'detect_lang'!")

        return attrs


    def get_url(self, obj):
        default_version = "v2"
        index = reverse(f"{default_version}:apply_snowball-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def to_representation(self, instance: ApplyStemmerWorker):
        data = super(ApplySnowballSerializer, self).to_representation(instance)
        data["query"] = json.loads(instance.query)
        data["fields"] = json.loads(instance.fields)
        return data


    class Meta:
        model = ApplyStemmerWorker
        fields = ("id", "url", "author_username", "indices", "stemmer_lang", "fields", "es_timeout", "bulk_size", "detect_lang", "description", "task", "query",)
