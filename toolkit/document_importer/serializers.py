from rest_framework import serializers


class ElasticDocumentSerializer(serializers.Serializer):
    _id = serializers.CharField(required=False)
    _index = serializers.CharField(default=None)
    _type = serializers.CharField(default=None)
    _source = serializers.DictField(required=True)


class InsertDocumentsSerializer(serializers.Serializer):
    documents = ElasticDocumentSerializer(many=True)
    split_text_in_fields = serializers.ListSerializer(child=serializers.CharField(), default=["text"])


class UpdateSplitDocumentSerializer(serializers.Serializer):
    id_field = serializers.CharField()
    text_field = serializers.CharField()
    content = serializers.CharField()
