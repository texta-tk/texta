import json
import re

from django.urls import reverse
from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.serializers import TaskSerializer
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.serializer_constants import CommonModelSerializerMixin, FieldParseSerializer, IndicesSerializerMixin
from toolkit.settings import REST_FRAMEWORK
from toolkit.topic_analyzer.choices import CLUSTERING_ALGORITHMS, VECTORIZERS
from toolkit.topic_analyzer.models import Cluster, ClusteringResult
from toolkit.topic_analyzer.validators import check_cluster_existence


class TransferClusterDocumentsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField(), required=True, allow_empty=False)
    receiving_cluster_id = serializers.IntegerField(min_value=0, required=True, validators=[check_cluster_existence])


class ClusteringIdsSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.CharField())


class ClusterSerializer(serializers.ModelSerializer):
    document_ids = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    fields = serializers.ListField(child=serializers.CharField())
    display_fields = serializers.ListField(child=serializers.CharField())
    significant_words = serializers.ListField(child=serializers.DictField(), allow_empty=True)
    document_count = serializers.SerializerMethodField()
    intracluster_similarity = serializers.FloatField()


    def get_document_count(self, obj):
        documents = json.loads(obj.document_ids)
        return len(documents)


    def to_representation(self, instance):
        data = super(ClusterSerializer, self).to_representation(instance)
        data["significant_words"] = json.loads(instance.significant_words)
        data["document_ids"] = json.loads(instance.document_ids)
        data["fields"] = json.loads(instance.fields)
        data["display_fields"] = json.loads(instance.display_fields)
        return data


    class Meta:
        model = Cluster
        fields = "__all__"


class ClusteringSerializer(FieldParseSerializer, serializers.ModelSerializer, CommonModelSerializerMixin, IndicesSerializerMixin):
    query = serializers.CharField(help_text='Query in JSON format', default=EMPTY_QUERY)
    num_cluster = serializers.IntegerField(min_value=1, max_value=1000, default=10, help_text='Number of document clusters to be formed.')
    clustering_algorithm = serializers.ChoiceField(choices=CLUSTERING_ALGORITHMS, default=CLUSTERING_ALGORITHMS[0][0], required=False)
    fields = serializers.ListField(required=True, help_text='Fields that are used for clustering')
    display_fields = serializers.ListField(default=[], allow_empty=True, help_text='Fields that are used for displaying cluster content. If not specified it is same as "fields".')
    vectorizer = serializers.ChoiceField(choices=VECTORIZERS, default=VECTORIZERS[0][0])
    num_dims = serializers.IntegerField(min_value=1, max_value=10000, default=1000, help_text='Size of the dictionary.')
    use_lsi = serializers.BooleanField(default=False, help_text='If set to 1 (true), transforms document-term matrix into lower-dimensional space using LSI. Might and might not improve clustering results.')
    num_topics = serializers.IntegerField(min_value=1, max_value=1000, default=50, help_text='Is only used if use_lsi is set to 1. The number of dimension in lower-dimensional space.')

    stop_words = serializers.ListField(default=[], allow_empty=True, help_text='List of custom stop words to be removed from documents before clustering.')
    document_limit = serializers.IntegerField(default=100, min_value=1, max_value=10000, help_text='Number of documents retrieved from indices.')
    ignored_ids = serializers.ListField(default=[], help_text="List of Elasticsearch document ids to ignore from the clustering process.")
    significant_words_filter = serializers.CharField(help_text='Regex to filter out desired words.', default="[0-9]+")

    url = serializers.SerializerMethodField()


    def get_url(self, obj):
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")
        if default_version == "v1":
            index = reverse(f"{default_version}:clustering-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        elif default_version == "v2":
            index = reverse(f"{default_version}:topic_analyzer-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def validate_significant_words_filter(self, regex):
        try:
            re.compile(regex)
        except re.error:
            raise serializers.ValidationError("Given string is not a valid regex.")
        return regex


    class Meta:
        model = ClusteringResult
        fields = [
            "id", "url", "description", "author", "query", "indices", "num_cluster", "clustering_algorithm",
            "vectorizer", "num_dims", "use_lsi", "num_topics", "significant_words_filter", "display_fields",
            "stop_words", "ignored_ids", "fields", "embedding", "document_limit", "tasks"
        ]
        fields_to_parse = ("fields", "query", "display_fields", "ignored_ids", "stop_words")
