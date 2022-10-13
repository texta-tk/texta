import json
import os

from texta_tools.text_processor import TextProcessor

import rest_framework.filters as drf_filters
from django.http import HttpResponse
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.index.models import Index
from toolkit.embedding.models import Embedding
from toolkit.embedding.serializers import EmbeddingPredictSimilarWordsSerializer, EmbeddingSerializer
from toolkit.exceptions import NonExistantModelError, ProjectValidationFailed, SerializerNotValid
from toolkit.filter_constants import FavoriteFilter
from toolkit.permissions.project_permissions import ProjectAccessInApplicationsAllowed
from toolkit.serializer_constants import GeneralTextSerializer, ProjectResourceImportModelSerializer
from toolkit.view_constants import BulkDelete, FavoriteModelViewMixing


class EmbeddingFilter(FavoriteFilter):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('tasks__status', lookup_expr='icontains')


    class Meta:
        model = Embedding
        fields = []


class EmbeddingViewSet(viewsets.ModelViewSet, BulkDelete, FavoriteModelViewMixing):
    queryset = Embedding.objects.all()
    serializer_class = EmbeddingSerializer
    permission_classes = (
        ProjectAccessInApplicationsAllowed,
        permissions.IsAuthenticated,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = EmbeddingFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'tasks__time_started', 'tasks__time_completed', 'num_dimensions', 'min_freq', 'vocab_size', 'tasks__status')


    @action(detail=False, methods=["post"], serializer_class=ProjectResourceImportModelSerializer)
    def import_model(self, request, pk=None, project_pk=None):
        serializer = ProjectResourceImportModelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data['file']
        embedding_id = Embedding.import_resources(uploaded_file, request, project_pk)
        return Response({"id": embedding_id, "message": "Successfully imported model and associated files."}, status=status.HTTP_201_CREATED)


    @action(detail=True, methods=['get'])
    def export_model(self, request, pk=None, project_pk=None):
        """Returns list of tags for input text."""
        zip_name = f'embedding_model_{pk}.zip'
        embedding_object: Embedding = self.get_object()
        data = embedding_object.export_resources()
        response = HttpResponse(data)
        response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(zip_name)
        return response


    def get_queryset(self):
        return Embedding.objects.filter(project=self.kwargs['project_pk']).order_by('-id')


    def perform_create(self, serializer):
        project = Project.objects.get(id=self.kwargs['project_pk'])
        indices = [index["name"] for index in serializer.validated_data["indices"]]
        indices = project.get_available_or_all_project_indices(indices)

        # If no indices are sent with the request, it gets all.
        # If all indices still means none, then we have a problem.
        if indices is not None:
            serializer.validated_data.pop("indices")
            embedding: Embedding = serializer.save(
                author=self.request.user,
                project=Project.objects.get(id=self.kwargs['project_pk']),
                fields=json.dumps(serializer.validated_data['fields']),
                stop_words=json.dumps(serializer.validated_data["stop_words"], ensure_ascii=False)
            )

            for index in Index.objects.filter(name__in=indices, is_open=True):
                embedding.indices.add(index)

            embedding.train()
        else:
            raise ValidationError("Can't train Embedding with zero configured indices.")


    def destroy(self, request, *args, **kwargs):
        instance: Embedding = self.get_object()
        instance.delete()
        return Response({"success": "Models removed"}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['post'], serializer_class=EmbeddingPredictSimilarWordsSerializer)
    def predict_similar(self, request, pk=None, project_pk=None):
        """Returns predictions of similar items to input words/phrases."""

        serializer = EmbeddingPredictSimilarWordsSerializer(data=request.data)
        if serializer.is_valid():

            embedding_object = self.get_object()
            if not embedding_object.embedding_model.path:
                raise NonExistantModelError()

            embedding = embedding_object.get_embedding()
            embedding.load_django(embedding_object)

            predictions = embedding.get_similar(
                serializer.validated_data['positives_used'],
                negatives_used = serializer.validated_data['negatives_used'],
                positives_unused = serializer.validated_data['positives_unused'],
                negatives_unused = serializer.validated_data['negatives_unused'],
                n=serializer.validated_data['output_size']
            )
            return Response(predictions, status=status.HTTP_200_OK)
        else:
            raise SerializerNotValid(detail=serializer.errors)


    @action(detail=True, methods=['post'], serializer_class=GeneralTextSerializer)
    def phrase_text(self, request, pk=None, project_pk=None):
        """Returns phrased version of input text. Phrasing is done using Gensim phraser trained with the embedding."""
        data = request.data
        serializer = GeneralTextSerializer(data=data)
        if serializer.is_valid():

            embedding_object = self.get_object()
            if not embedding_object.embedding_model.name:
                raise NonExistantModelError()

            embedding = embedding_object.get_embedding()
            embedding.load_django(embedding_object)
            phraser = embedding.phraser

            text_processor = TextProcessor(phraser=phraser, remove_stop_words=False)
            phrased_text = text_processor.process(serializer.validated_data['text'])

            return Response(phrased_text, status=status.HTTP_200_OK)
        else:
            raise SerializerNotValid(detail=serializer.errors)
