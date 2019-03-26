from rest_framework import serializers

from toolkit.datasets.models import Dataset


class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ('id', 'author', 'project' , 'index', 'mapping')