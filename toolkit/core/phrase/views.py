from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.phrase.models import Phrase
from toolkit.core.phrase.serializers import PhraseSerializer


class PhraseViewSet(viewsets.ModelViewSet):
    queryset = Phrase.objects.all()
    serializer_class = PhraseSerializer
