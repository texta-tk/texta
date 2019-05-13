from rest_framework import serializers
from toolkit.tagger.models import Tagger


class HybridTaggerSerializer(serializers.Serializer):
    taggers = serializers.PrimaryKeyRelatedField(queryset=Tagger.objects.all(), many=True)
