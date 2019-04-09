from rest_framework import serializers

class EntitySerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.CharField()