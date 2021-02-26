from rest_framework import serializers


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
