from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core import permissions as core_permissions
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.embedding.serializers import (EmbeddingSerializer, EmbeddingPrecictionSerializer, TextSerializer,
                                           EmbeddingClusterSerializer, ClusterBrowserSerializer)
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.embedding.phraser import Phraser
from toolkit.embedding.word_cluster import WordCluster
from toolkit.utils.model_cache import ModelCache
from toolkit import permissions as toolkit_permissions
from toolkit.tools.text_processor import TextProcessor

import json

w2v_cache = ModelCache(W2VEmbedding)
phraser_cache = ModelCache(Phraser)
cluster_cache = ModelCache(WordCluster)


def get_payload(request):
    if request.GET:
        data = request.GET
    elif request.POST:
        data = request.POST
    else:
        data = {}
    return data


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


    @action(detail=True, methods=['get', 'post'],serializer_class=EmbeddingPrecictionSerializer)
    def predict(self, request, pk=None, project_pk=None):
        data = get_payload(request)
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

    @action(detail=True, methods=['get', 'post'], serializer_class=TextSerializer)
    def phrase(self, request, pk=None, project_pk=None):
        data = get_payload(request)
        serializer = TextSerializer(data=data)
        if serializer.is_valid():
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

            phraser = phraser_cache.get_model(embedding_object.pk)
            text_processor = TextProcessor(phraser=phraser, sentences=False, remove_stop_words=False, tokenize=False)
            phrased_text = text_processor.process(serializer.validated_data['text'])[0]
            
            return Response(phrased_text, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class EmbeddingClusterViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows TEXTA embedding clusterings to be viewed or edited.
    Only include embedding clusterings that are related to the request UserProfile's active_project
    """
    serializer_class = EmbeddingClusterSerializer
    permission_classes = (
        core_permissions.TaggerEmbeddingsPermissions, 
        permissions.IsAuthenticated,
        toolkit_permissions.HasActiveProject
    )

    def get_queryset(self):
        queryset = EmbeddingCluster.objects.all()
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = EmbeddingCluster.objects.filter(project=current_user.profile.active_project)
        return queryset
    
    
    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=self.request.user.profile.active_project)


    @action(detail=True, methods=['get', 'post'], serializer_class=ClusterBrowserSerializer)
    def browse(self, request, pk=None):
        """
        API endpoint for browsing clustering results.
        """
        data = get_payload(request)
        serializer = ClusterBrowserSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        clustering_object = self.get_object()
        # check if clustering ready
        if not clustering_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # load cluster model
        clusterer = cluster_cache.get_model(clustering_object.pk)


        clustering_result = clusterer.browse(max_examples_per_cluster=serializer.validated_data['max_examples_per_cluster'],
                                             number_of_clusters=serializer.validated_data['number_of_clusters'],
                                             sort_reverse=serializer.validated_data['cluster_order'])

        return Response(clustering_result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get', 'post'], serializer_class=TextSerializer)
    def find_word(self, request, pk=None):
        """
        API endpoint for finding a cluster for any word in model.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        clustering_object = self.get_object()
        # check if clustering ready
        if not clustering_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # load cluster model
        clusterer = cluster_cache.get_model(clustering_object.pk)

        clustering_result = clusterer.query(serializer.validated_data['text'])
        return Response(clustering_result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=TextSerializer)
    def cluster_text(self, request, pk=None):
        """
        API endpoint for clustering raw text.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
        
        clustering_object = self.get_object()
        # check if clustering ready
        if not clustering_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # load cluster model
        clusterer = cluster_cache.get_model(clustering_object.pk)

        clustered_text = clusterer.text_to_clusters(serializer.validated_data['text'])
        return Response(clustered_text, status=status.HTTP_200_OK)