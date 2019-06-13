from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core import permissions as core_permissions
from toolkit.embedding.models import Embedding
from toolkit.embedding.serializers import EmbeddingSerializer, EmbeddingPrecictionSerializer, PhrasePrecictionSerializer
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.embedding.phraser import Phraser
from toolkit.utils.model_cache import ModelCache
from toolkit import permissions as toolkit_permissions

import json

w2v_cache = ModelCache(W2VEmbedding)
phraser_cache = ModelCache(Phraser)

class EmbeddingViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    Only include the embeddings that are related to the request UserProfile's active_project
    """
    serializer_class = EmbeddingSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions, 
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
    )

    def get_queryset(self):
        queryset = Embedding.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = Embedding.objects.filter(project=current_user.profile.active_project)
        return queryset
    
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)


    @staticmethod
    def get_payload(request):
        if request.GET:
            data = request.GET
        elif request.POST:
            data = request.POST
        else:
            data = {}
        return data

    @action(detail=True, methods=['get', 'post'],serializer_class=EmbeddingPrecictionSerializer)
    def predict(self, request, pk=None, project_pk=None):
        data = self.get_payload(request)
        serializer = EmbeddingPrecictionSerializer(data=data)
        if serializer.is_valid():
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
            
            embedding = w2v_cache.get_model(embedding_object.pk)

            predictions = embedding.get_similar(serializer.validated_data['text'], n=serializer.validated_data['output_size'])
            return Response(predictions, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get', 'post'], serializer_class=PhrasePrecictionSerializer)
    def phrase(self, request, pk=None, project_pk=None):
        data = self.get_payload(request)
        serializer = PhrasePrecictionSerializer(data=data)
        if serializer.is_valid():
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

            phraser = phraser_cache.get_model(embedding_object.pk)
            phrased_text = phraser.phrase(serializer.validated_data['text'])
            return Response(phrased_text, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)