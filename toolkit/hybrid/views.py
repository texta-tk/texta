from rest_framework import viewsets, status
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.tagger.models import Tagger
from toolkit.hybrid.serializers import HybridTaggerSerializer
from toolkit.tagger.text_tagger import TextTagger


class HybridTaggerViewSet(viewsets.ViewSet):
    """
    API endpoint that allows tagger models to be viewed or edited.
    """

    def list(self, request):
        #serializer = serializers.TaskSerializer(
        #    instance=tasks.values(), many=True)

        return Response([])