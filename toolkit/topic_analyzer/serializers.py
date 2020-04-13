import json

from django.urls import reverse
from rest_framework import serializers

from toolkit.core.task.serializers import TaskSerializer
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.elastic.serializers import IndexSerializer
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
        return data


    class Meta:
        model = Cluster
        fields = "__all__"


class ClusteringSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    description = serializers.CharField()
    query = serializers.CharField(help_text='Query in JSON format', default=EMPTY_QUERY)
    num_cluster = serializers.IntegerField(min_value=1, max_value=1000, default=10)
    clustering_algorithm = serializers.ChoiceField(choices=CLUSTERING_ALGORITHMS, default=CLUSTERING_ALGORITHMS[0][0], required=False)
    fields = serializers.ListField(required=True)
    original_text_field = serializers.CharField(default="")
    vectorizer = serializers.ChoiceField(choices=VECTORIZERS, default=VECTORIZERS[0][0])
    num_dims = serializers.IntegerField(min_value=1, max_value=10000, default=1000)
    use_lsi = serializers.BooleanField(default=False)
    num_topics = serializers.IntegerField(min_value=1, max_value=1000, default=50)

    stop_words = serializers.ListField(default=[], allow_empty=True)
    document_limit = serializers.IntegerField(default=100, min_value=1, max_value=10000)
    indices = IndexSerializer(many=True, default=[])
    ignored_ids = serializers.ListField(default=[])

    url = serializers.SerializerMethodField()
    task = TaskSerializer(read_only=True)


    def get_url(self, obj):
        index = reverse("v1:clustering-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def to_representation(self, instance):
        data = super(ClusteringSerializer, self).to_representation(instance)
        data["stop_words"] = json.loads(instance.stop_words)
        data["ignored_ids"] = json.loads(instance.ignored_ids)
        data["fields"] = json.loads(instance.fields)
        data["query"] = json.loads(instance.query)
        return data


    class Meta:
        model = ClusteringResult
        fields = [
            "id", "url", "description", "author_username", "query", "indices", "num_cluster", "clustering_algorithm",
            "vectorizer", "num_dims", "use_lsi", "num_topics", "original_text_field",
            "stop_words", "ignored_ids", "fields", "document_limit", "task"
        ]
