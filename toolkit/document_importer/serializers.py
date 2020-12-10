from rest_framework import serializers


class ElasticDocumentSerializer(serializers.Serializer):
    _id = serializers.CharField(required=False)
    _index = serializers.CharField(required=True)
    _type = serializers.CharField(required=False)
    _source = serializers.DictField(required=True)


class InsertDocumentsSerializer(serializers.Serializer):
    documents = ElasticDocumentSerializer(many=True)
