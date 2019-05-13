from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.phrase.models import Phrase
from toolkit.core.phrase.serializers import PhraseSerializer

# Create your views here.
class PhraseViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Phrase.objects.all()
    serializer_class = PhraseSerializer
