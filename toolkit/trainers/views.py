from django.shortcuts import render
from rest_framework import viewsets

from toolkit.trainers.models import Embedding, Tagger, Task
from toolkit.trainers.serializers import EmbeddingSerializer, TaggerSerializer, TaskSerializer

class EmbeddingViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer


class TaggerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Tagger.objects.all()
    serializer_class = TaggerSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA tasks to be viewed or edited.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
