from rest_framework import serializers

class Entity(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

class EntitySerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.CharField()

