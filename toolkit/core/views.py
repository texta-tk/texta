from django.shortcuts import render
from django.contrib.auth.models import User
from rest_framework import viewsets

from toolkit.core.models import Project, Search, Dataset, Lexicon, Phrase
from toolkit.core.serializers import UserSerializer, ProjectSerializer, DatasetSerializer, SearchSerializer, LexiconSerializer, PhraseSerializer


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


class DatasetViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows projects to be viewed or edited.
    """
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer


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
