from rest_framework import serializers
from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import SimpleTaggerSerializer


class HybridTaggerTextSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.all(), many=True)
    text = serializers.CharField()
    hybrid_mode = serializers.BooleanField()


class HybridTaggerDocSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.all(), many=True)
    doc = serializers.JSONField()
