from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.lexicon.models import Lexicon
from toolkit.core.lexicon.serializers import LexiconSerializer

# Create your views here.
class LexiconViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Lexicon.objects.all()
    serializer_class = LexiconSerializer
