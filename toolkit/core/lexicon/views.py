from django.shortcuts import render
from rest_framework import viewsets

from toolkit.core.lexicon.models import Lexicon
from toolkit.core.lexicon.serializers import LexiconSerializer


class LexiconViewSet(viewsets.ModelViewSet):
    queryset = Lexicon.objects.all()
    serializer_class = LexiconSerializer
