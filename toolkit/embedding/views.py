from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core import permissions
from toolkit.embedding.models import Embedding
from toolkit.embedding.serializers import EmbeddingSerializer, PredictionSerializer, PhraserSerializer
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.embedding.phraser import Phraser

import json

class EmbeddingViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    Only include the embeddings that are related to the request UserProfile's active_project
    """
    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer
    permission_classes = (permissions.TaggerEmbeddingsPermissions,)

    def get_queryset(self):
        assert self.queryset is not None, (
            "'%s' should either include a `queryset` attribute, "
            "or override the `get_queryset()` method."
            % self.__class__.__name__
        )
        queryset = self.queryset
        if not self.request.user.is_superuser:
            queryset = Embedding.objects.filter(project=self.request.user.profile.active_project)
        return queryset


    @staticmethod
    def get_payload(request):
        if request.GET:
            data = request.GET
        elif request.POST:
            data = request.POST
        else:
            data = {}
        return data

    @action(detail=True, methods=['get', 'post'])
    def predict(self, request, pk=None, project_pk=None):
        data = self.get_payload(request)
        serializer = PredictionSerializer(data=data)
        if serializer.is_valid():
            data = serializer.data
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
            embedding = W2VEmbedding(embedding_id=embedding_object.pk)
            embedding.load()
            predictions = embedding.get_similar(data['phrase'], n=10)
            return Response(predictions, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'])
    def phrase(self, request, pk=None, project_pk=None):
        data = self.get_payload(request)
        serializer = PhraserSerializer(data=data)
        if serializer.is_valid():
            data = serializer.data
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
            phraser = Phraser(embedding_id=embedding_object.pk)
            phraser.load()
            phrased_text = phraser.phrase(data['text'])
            print(data['text'])
            return Response(phrased_text, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
