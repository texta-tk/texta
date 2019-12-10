import json

import rest_framework.filters as drf_filters
from django_filters import rest_framework as filters
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.exceptions import NonExistantModelError, ProjectValidationFailed, SerializerNotValid
from toolkit.neurotagger.models import Neurotagger
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
from toolkit.neurotagger.serializers import NeuroTaggerTagDocumentSerializer, NeuroTaggerTagTextSerializer, NeurotaggerSerializer
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.view_constants import BulkDelete, ExportModel, TagLogicViews


class NeuroTaggerFilter(filters.FilterSet):
    description = filters.CharFilter('description', lookup_expr='icontains')
    task_status = filters.CharFilter('task__status', lookup_expr='icontains')


    class Meta:
        model = Neurotagger
        fields = []


class NeurotaggerViewSet(viewsets.ModelViewSet, TagLogicViews, BulkDelete, ExportModel):
    """
    list:
    Returns list of Neurotagger objects.

    read:
    Return Neurotagger object by id.

    create:
    Creates Neurotagger object.

    update:
    Updates entire Neurotagger object.

    partial_update:
    Performs partial update on Neurotagger object.

    delete:
    Deletes Neurotagger object.
    """
    serializer_class = NeurotaggerSerializer
    permission_classes = (
        permissions.IsAuthenticated,
        ProjectResourceAllowed,
    )

    filter_backends = (drf_filters.OrderingFilter, filters.DjangoFilterBackend)
    filterset_class = NeuroTaggerFilter
    ordering_fields = ('id', 'author__username', 'description', 'fields', 'task__time_started', 'task__time_completed', 'training_loss', 'training_accuracy',
                       'validation_accuracy', 'validation_loss', 'task__status')


    def get_queryset(self):
        return Neurotagger.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer, **kwargs):
        neurotagger = serializer.save(
            author=self.request.user,
            project=Project.objects.get(id=self.kwargs['project_pk']),
            fields=json.dumps(serializer.validated_data['fields']),
            **kwargs
        )
        neurotagger.train()


    def perform_update(self, serializer):
        serializer.save(fields=json.dumps(serializer.validated_data['fields']))


    def create(self, request, *args, **kwargs):
        serializer = NeurotaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # raise error on neurotagger empty fields
        project_fields = set(Project.objects.get(id=self.kwargs['project_pk']).get_elastic_fields(path_list=True))
        entered_fields = set(serializer.validated_data['fields'])
        if not entered_fields:
            raise ProjectValidationFailed(detail=f'entered fields not in current project fields: {project_fields}')
        if 'fact_name' in serializer.validated_data and serializer.validated_data['fact_name']:
            fact_name = serializer.validated_data['fact_name']
            active_project = Project.objects.get(id=self.kwargs['project_pk'])
            # Retrieve tags/fact values and create queries to build models. Every tag will be a class.
            tags = self.get_tags(
                fact_name,
                active_project,
                min_count=serializer.validated_data['min_fact_doc_count'],
                max_count=serializer.validated_data['max_fact_doc_count']
            )
            # Check if any tags were found
            if not tags:
                return Response({'error': f'found no tags for fact name: {fact_name}'}, status=status.HTTP_400_BAD_REQUEST)

            # Create queries for each fact
            queries = json.dumps(self.create_queries(fact_name, tags))
            self.perform_create(serializer, fact_values=json.dumps(tags), queries=queries)
        else:
            return Response({"error": "Tag name must be included!"}, status=status.HTTP_400_BAD_REQUEST)

        headers = self.get_success_headers(serializer.data)

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def destroy(self, request, *args, **kwargs):
        instance: Neurotagger = self.get_object()
        instance.delete()
        return Response({"success": f'Neurotagger instance "{instance.description}" deleted, models and plots were removed'}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['post'], serializer_class=NeuroTaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """Returns tags for input text."""
        serializer = NeuroTaggerTagTextSerializer(data=request.data)

        # check if valid request
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.model.name:
            raise NonExistantModelError()

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, serializer.validated_data['text'], threshold=serializer.validated_data['threshold'], input_type='text')
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=NeuroTaggerTagDocumentSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """Returns tags for input document."""
        serializer = NeuroTaggerTagDocumentSerializer(data=request.data)

        # check if valid request
        if not serializer.is_valid():
            raise SerializerNotValid(detail=serializer.errors)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.model.path:
            raise NonExistantModelError()

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, serializer.data['doc'], threshold=serializer.validated_data['threshold'], input_type='doc')
        return Response(tagger_response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_object, tagger_input, threshold=0.0000001, input_type='text'):
        tagger = NeurotaggerWorker(tagger_object.id)
        tagger.load()

        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)

        classes = json.loads(self.get_object().fact_values)
        probabilities = list(tagger_result[0])
        tag_data = [{'tag': label, 'probability': probability} for label, probability in zip(classes, probabilities) if probability > threshold]
        tag_data = sorted(tag_data, key=lambda k: k['probability'], reverse=True)

        result = {'tags': tag_data}

        return result


    @action(detail=True, methods=['get'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns list of tags for a random document in Elasticsearch."""

        tagger_object = self.get_object()  # get tagger object
        tagger_fields = json.loads(tagger_object.fields)  # retrieve tagger fields
        tagger_id = tagger_object.id

        # check if tagger exists
        if not tagger_object.model.name:
            raise NonExistantModelError()
        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)

        if not ElasticCore().check_if_indices_exist(tagger_object.project.indices):
            return Response({'error': f'One or more index from {list(tagger_object.project.indices)} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve random document
        random_doc = ElasticSearcher(indices=tagger_object.project.indices).random_documents(size=1)[0]
        # filter out correct fields from the document
        random_doc_filtered = {k: v for k, v in random_doc.items() if k in tagger_fields}
        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)
