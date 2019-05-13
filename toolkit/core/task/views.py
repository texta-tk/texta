from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.task.models import Task
from toolkit.core.task.serializers import TaskSerializer

# Create your views here.
class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA tasks to be viewed or edited.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
