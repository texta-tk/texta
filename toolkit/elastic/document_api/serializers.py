import json

from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.elastic.document_api.models import DeleteFactsByQueryTask, EditFactsByQueryTask
from toolkit.serializer_constants import CommonModelSerializerMixin, IndicesSerializerMixin, ProjectResourceUrlSerializer, QUERY_HELPTEXT


class ElasticDocumentSerializer(serializers.Serializer):
    _id = serializers.CharField(required=False, help_text="Under which id should Elasticsearch insert the document, without this Elasticsearch will generate one itself.")
    _index = serializers.CharField(default=None, help_text="Under which index should Elasticsearch insert the document, lacking one Toolkit will generate one automatically.")
    _source = serializers.DictField(required=True, help_text="Actual content of the document.")


class InsertDocumentsSerializer(serializers.Serializer):
    documents = ElasticDocumentSerializer(many=True, help_text="Collection of raw Elasticsearch documents.")
    split_text_in_fields = serializers.ListSerializer(child=serializers.CharField(), default=["text"], help_text="Specifies which text fields should be split into smaller pieces.")


class UpdateSplitDocumentSerializer(serializers.Serializer):
    id_field = serializers.CharField(help_text="Which field to use as the ID marker to categorize split documents into a single entity.")
    id_value = serializers.CharField(help_text="Value of the ID field by which you categorize split documents into a single entity.")
    text_field = serializers.CharField(help_text="Specifies the name of the text field you wish to update.")
    content = serializers.CharField(help_text="New content that the old one will be updated with.")


class FactSerializer(serializers.Serializer):
    num_val = serializers.IntegerField(required=False)
    spans = serializers.CharField(default=json.dumps([[0, 0]]))
    str_val = serializers.CharField(required=True)
    fact = serializers.CharField(required=True)
    doc_path = serializers.CharField(required=False)


class FactsSerializer(serializers.Serializer):
    facts = FactSerializer(many=True, default=[])


class UpdateFactsSerializer(serializers.Serializer):
    target_facts = FactSerializer(many=True, default=[])
    resulting_fact = FactSerializer(required=True)


class DeleteFactsByQuerySerializer(serializers.ModelSerializer, IndicesSerializerMixin, CommonModelSerializerMixin, ProjectResourceUrlSerializer):
    query = serializers.JSONField(help_text=QUERY_HELPTEXT, required=False, default=json.dumps(EMPTY_QUERY))
    url = serializers.SerializerMethodField()
    facts = serializers.ListField(child=serializers.DictField(), help_text=f'List of facts to remove from documents')


    def to_representation(self, instance):
        try:
            facts = json.loads(instance.facts)
        except Exception:
            facts = []

        try:
            query = json.loads(instance.query)
        except Exception:
            query = {}

        instance.facts = facts
        instance.query = query
        data = super(DeleteFactsByQuerySerializer, self).to_representation(instance)
        return data


    class Meta:
        model = DeleteFactsByQueryTask
        fields = ('id', 'url', 'author', 'description', 'query', 'facts', 'indices', 'tasks')


class EditFactsByQuerySerializer(serializers.ModelSerializer, IndicesSerializerMixin, CommonModelSerializerMixin, ProjectResourceUrlSerializer):
    query = serializers.JSONField(help_text=QUERY_HELPTEXT, required=False, default=json.dumps(EMPTY_QUERY))
    url = serializers.SerializerMethodField()
    target_facts = serializers.ListField(child=serializers.DictField(), help_text=f'List of facts to edit from documents')
    fact = serializers.JSONField(help_text="How the targeted facts should be changed into.")


    def to_representation(self, instance):
        try:
            target_facts = json.loads(instance.target_facts)
        except Exception:
            target_facts = []

        try:
            query = json.loads(instance.query)
        except Exception:
            query = {}

        try:
            fact = json.loads(instance.fact)
        except Exception:
            fact = {}

        instance.target_facts = target_facts
        instance.query = query
        instance.fact = fact
        data = super(EditFactsByQuerySerializer, self).to_representation(instance)
        return data


    class Meta:
        model = EditFactsByQueryTask
        fields = ('id', 'url', 'author', 'description', 'query', 'target_facts', 'fact', 'indices', 'tasks')
