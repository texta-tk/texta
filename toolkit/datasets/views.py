from django.shortcuts import render
from rest_framework import viewsets

from toolkit.datasets.models import Dataset
from toolkit.datasets.serializers import DatasetSerializer


class DatasetViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows datasets to be viewed or edited.
    """
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer