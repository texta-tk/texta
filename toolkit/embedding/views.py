import os
import json

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.embedding.serializers import (EmbeddingSerializer, EmbeddingPredictSimilarWordsSerializer,
                                           EmbeddingClusterSerializer, EmbeddingClusterBrowserSerializer)
from toolkit.serializer_constants import GeneralTextSerializer
from toolkit.embedding.embedding import W2VEmbedding
from toolkit.embedding.phraser import Phraser
from toolkit.embedding.word_cluster import WordCluster
from toolkit.core.project.models import Project
from toolkit.tools.model_cache import ModelCache
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.tools.text_processor import TextProcessor
from toolkit.view_constants import BulkDelete, ExportModel

from django_filters import rest_framework as filters
import rest_framework.filters as drf_filters


global_w2v_cache = ModelCache(W2VEmbedding)
global_phraser_cache = ModelCache(Phraser)
global_cluster_cache = ModelCache(WordCluster)


class EmbeddingFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')

    class Meta:
        model = Embedding
        fields = []


class EmbeddingViewSet(viewsets.ModelViewSet, BulkDelete, ExportModel):
    """
    list:
    Returns list of Embedding objects.

    read:
    Return Embedding object by id.

    create:
    Creates Embedding object.

    update:
    Updates entire Embedding object.

    partial_update:
    Performs partial update on Embedding object.

    delete:
    Deletes Embedding object.
    """
    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = EmbeddingFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'num_dimensions', 'min_freq', 'vocab_size', 'task__status')

    def get_queryset(self):
        return Embedding.objects.filter(project=self.kwargs['project_pk'])

    def perform_create(self, serializer):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']))

    def perform_update(self, serializer):
        serializer.save(fields=json.dumps(serializer.validated_data['fields']))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        # try:
        embedding_model_location = json.loads(instance.location)['embedding']
        phraser_model_location = json.loads(instance.location)['phraser']
        os.remove(embedding_model_location)
        os.remove(phraser_model_location)
        return Response({"success": "Models removed"}, status=status.HTTP_204_NO_CONTENT)
        # except:
            # return Response({"success": "Embedding instance deleted, but models were not removed"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'],serializer_class=EmbeddingPredictSimilarWordsSerializer)
    def predict_similar(self, request, pk=None, project_pk=None):
        """Returns predictions of similar items to input words/phrases."""
        serializer = EmbeddingPredictSimilarWordsSerializer(data=request.data)
        if serializer.is_valid():
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

            embedding = global_w2v_cache.get_model(embedding_object)

            predictions = embedding.get_similar(serializer.validated_data['positives'],
                                                negatives=serializer.validated_data['negatives'],
                                                n=serializer.validated_data['output_size']
                                                )

            return Response(predictions, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def phrase_text(self, request, pk=None, project_pk=None):
        """Returns phrased version of input text. Phrasing is done using Gensim phraser trained with the embedding."""
        data = request.data
        serializer = GeneralTextSerializer(data=data)
        if serializer.is_valid():
            embedding_object = self.get_object()
            if not embedding_object.location:
                return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

            phraser = global_phraser_cache.get_model(embedding_object)
            text_processor = TextProcessor(phraser=phraser, sentences=False, remove_stop_words=False, tokenize=False)
            phrased_text = text_processor.process(serializer.validated_data['text'])[0]

            return Response(phrased_text, status=status.HTTP_200_OK)
        else:
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)


class EmbeddingClusterViewSet(viewsets.ModelViewSet, BulkDelete):
    """
    list:
    Returns list of Embedding Cluster objects.

    read:
    Return Embedding Cluster object by id.

    create:
    Creates Embedding Cluster object.

    update:
    Updates entire Embedding Cluster object.

    partial_update:
    Performs partial update on Embedding Cluster object.

    delete:
    Deletes Embedding Cluster object.
    """
    serializer_class = EmbeddingClusterSerializer
    permission_classes = (
        ProjectResourceAllowed,
        permissions.IsAuthenticated,
    )

    def get_queryset(self):
        return EmbeddingCluster.objects.filter(project=self.kwargs['project_pk'])

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, project=Project.objects.get(id=self.kwargs['project_pk']))


    @action(detail=True, methods=['post'], serializer_class=EmbeddingClusterBrowserSerializer)
    def browse_clusters(self, request, pk=None, project_pk=None):
        """Returns clustering results."""
        data = request.data
        serializer = EmbeddingClusterBrowserSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        clustering_object = self.get_object()
        # check if clustering ready
        if not clustering_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # load cluster model
        clusterer = global_cluster_cache.get_model(clustering_object)

        clustering_result = clusterer.browse(max_examples_per_cluster=serializer.validated_data['max_examples_per_cluster'],
                                             number_of_clusters=serializer.validated_data['number_of_clusters'],
                                             sort_reverse=serializer.validated_data['cluster_order'])

        return Response(clustering_result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def find_cluster_by_word(self, request, pk=None, project_pk=None):
        """Returns cluster id for input word."""
        data = request.data
        serializer = GeneralTextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        clustering_object = self.get_object()
        # check if clustering ready
        if not clustering_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # load cluster model
        clusterer = global_cluster_cache.get_model(clustering_object)

        clustering_result = clusterer.query(serializer.validated_data['text'])
        return Response(clustering_result, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def cluster_text(self, request, pk=None, project_pk=None):
        """Returns text with words replaced with cluster names in input text."""
        data = request.data
        serializer = GeneralTextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        clustering_object = self.get_object()
        # check if clustering ready
        if not clustering_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # load cluster model
        clusterer = global_cluster_cache.get_model(clustering_object)

        clustered_text = clusterer.text_to_clusters(serializer.validated_data['text'])
        return Response(clustered_text, status=status.HTTP_200_OK)
