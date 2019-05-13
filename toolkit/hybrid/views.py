from rest_framework import viewsets, status
from rest_framework.generics import GenericAPIView
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.tagger.models import Tagger
from toolkit.hybrid.serializers import HybridTaggerTextSerializer
from toolkit.hybrid.hybrid_tagger import HybridTagger


class HybridTaggerViewSet(viewsets.ViewSet):
    """
    API endpoint for using tagging models.
    """

    serializer_class = HybridTaggerTextSerializer

    
    def create(self, request):
        serializer = HybridTaggerTextSerializer(data=request.data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        print(request.data['taggers'])

        # apply hybrid tagger
        hybrid_tagger = HybridTagger()
        hybrid_tagger.load(request.data['taggers'])
        hybrid_tagger_response = hybrid_tagger.tag_text(request.data['text'])


        return Response(hybrid_tagger_response, status=status.HTTP_200_OK)
