from rest_framework import serializers


class AddFaceSerializer(serializers.Serializer):
    image = serializers.FileField()
    index = serializers.CharField()
    name = serializers.CharField(required=False, default="KNOWN_FACE")
    value = serializers.CharField(required=False, default="John Not Doe")


class FaceAnalyzerSerializer(serializers.Serializer):
    image = serializers.FileField()
    store_image = serializers.BooleanField(default=False)
    index = serializers.CharField(required=False)
