from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.tagger.models import Tagger
from toolkit.tagger.serializers import TaggerSerializer


class TaggerViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Tagger.objects.all()
    serializer_class = TaggerSerializer

    def get_queryset(self):
        return Tagger.objects.filter(project=self.request.user.profile.active_project)
