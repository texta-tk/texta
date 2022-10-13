import json

from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from .models import ApplyESAnalyzerWorker
from ..choices import DEFAULT_ELASTIC_TOKENIZER, DEFAULT_SNOWBALL_LANGUAGE, ELASTIC_TOKENIZERS, get_snowball_choices
from ...serializer_constants import TasksMixinSerializer, ToolkitTaskSerializer


class ApplyESAnalyzerWorkerSerializer(serializers.ModelSerializer, ToolkitTaskSerializer, TasksMixinSerializer):
    url = serializers.SerializerMethodField()

    analyzers = serializers.MultipleChoiceField(allow_blank=False, choices=(("stemmer", "stemmer"), ("tokenizer", "tokenizer")))
    strip_html = serializers.BooleanField(default=True, help_text="Whether to strip HTML from the text.")

    tokenizer = serializers.ChoiceField(choices=ELASTIC_TOKENIZERS, default=DEFAULT_ELASTIC_TOKENIZER, help_text="Which Elasticsearch tokenizer to use for tokenizer and stemmer analyzers.")
    stemmer_lang = serializers.ChoiceField(choices=get_snowball_choices(), default=DEFAULT_SNOWBALL_LANGUAGE, help_text="Which language stemmer to use.")
    detect_lang = serializers.BooleanField(default=False, help_text="Whether to automatically detect the language from the fields for stemming purposes.")
    bulk_size = serializers.IntegerField(min_value=0, max_value=500, default=100, help_text="How many items should be processed at once for Elasticsearch")
    es_timeout = serializers.IntegerField(min_value=1, max_value=100, default=30, help_text="How long should the timeout for scroll be in minutes.")


    def validate(self, attrs):
        if "stemmer" in attrs["analyzers"]:
            stemmer_lang_exists = "stemmer_lang" in attrs and attrs["stemmer_lang"]
            detect_lang_exists = "detect_lang" in attrs and attrs["detect_lang"]
            if stemmer_lang_exists and detect_lang_exists:
                raise ValidationError("Fields 'stemmer_lang' and 'detect_lang' are mutually exclusive, please choose one!")

            if not stemmer_lang_exists and not detect_lang_exists:
                raise ValidationError("Please choose at least one of the fields 'stemmer_lang' or 'detect_lang'!")

        return attrs


    def get_url(self, obj):
        default_version = "v2"
        index = reverse(f"{default_version}:apply_analyzers-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def to_representation(self, instance: ApplyESAnalyzerWorker):
        data = super(ApplyESAnalyzerWorkerSerializer, self).to_representation(instance)
        data["query"] = json.loads(instance.query)
        data["fields"] = json.loads(instance.fields)
        data["analyzers"] = json.loads(instance.analyzers)
        return data


    class Meta:
        model = ApplyESAnalyzerWorker
        fields = ("id", "url", "author", "strip_html", "indices", "analyzers", "stemmer_lang", "fields", "tokenizer", "es_timeout", "bulk_size", "detect_lang", "description", "tasks", "query",)


class SnowballSerializer(serializers.Serializer):
    text = serializers.CharField()
    language = serializers.ChoiceField(choices=get_snowball_choices(), required=True)
