from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.embedding.models import Embedding
from toolkit.embedding.serializers import EmbeddingSerializer
from toolkit.embedding.embedding import W2VEmbedding

import json

class EmbeddingViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer

    @action(detail=True, methods=['get', 'post'])
    def predict(self, request, pk=None):
        embedding_object = self.get_object()
        if not embedding_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        location = json.loads(embedding_object.location)

        embedding = W2VEmbedding()
        embedding.load(location['embedding'])
        
        if request.GET:
            data = request.GET
        elif request.POST:
            data = request.POST
        else:
            data = {}
        
        predictions = []
        if 'phrase' in data:
            phrase = data['phrase']
            predictions = embedding.get_similar(phrase, n=10)
        return Response(predictions)
