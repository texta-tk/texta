from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import viewsets

from toolkit.core.models import Project, Search, Lexicon, Phrase, Task
from toolkit.core.serializers import UserSerializer, ProjectSerializer, SearchSerializer, LexiconSerializer, PhraseSerializer, TaskSerializer


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer


class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer


class SearchViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows sear4ches to be viewed or edited.
    """
    queryset = Search.objects.all()
    serializer_class = SearchSerializer


class LexiconViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Lexicon.objects.all()
    serializer_class = LexiconSerializer


class PhraseViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Phrase.objects.all()
    serializer_class = PhraseSerializer


class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA tasks to be viewed or edited.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
