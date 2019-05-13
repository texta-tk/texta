from rest_framework import serializers
from toolkit.tagger.models import Tagger


class HybridTaggerTextSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.all(), many=True)
    text = serializers.CharField()

class HybridTaggerDocSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.all(), many=True)
    doc = serializers.JSONField()