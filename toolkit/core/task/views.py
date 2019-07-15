from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.task.models import Task
from toolkit.core.task.serializers import TaskSerializer


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
