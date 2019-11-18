import os
import json
import numpy as np

from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query

from toolkit.neurotagger.models import Neurotagger
from toolkit.core.project.models import Project
from toolkit.neurotagger.serializers import NeurotaggerSerializer
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
from toolkit.tools.model_cache import ModelCache
from toolkit import permissions as toolkit_permissions
from toolkit.view_constants import TagLogicViews
from toolkit.permissions.project_permissions import ProjectResourceAllowed
from toolkit.neurotagger.serializers import NeuroTaggerTagTextSerializer, NeuroTaggerTagDocumentSerializer
from toolkit.view_constants import BulkDelete, ExportModel

# initialize model cache for neurotaggers
model_cache = ModelCache(NeurotaggerWorker)

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


    def get_queryset(self):
        return Neurotagger.objects.filter(project=self.kwargs['project_pk'])


    def perform_create(self, serializer, **kwargs):
        serializer.save(author=self.request.user,
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']),
                        **kwargs)


    def perform_update(self, serializer):
        serializer.save(fields=json.dumps(serializer.validated_data['fields']))


    def create(self, request, *args, **kwargs):
        serializer = NeurotaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        # raise error on neurotagger empty fields
        project_fields = set(Project.objects.get(id=self.kwargs['project_pk']).get_elastic_fields(path_list=True))
        entered_fields = set(serializer.validated_data['fields'])
        if not entered_fields:
            return Response({'error': f'entered fields not in current project fields: {project_fields}'}, status=status.HTTP_400_BAD_REQUEST)

        if 'fact_name' in serializer.validated_data and serializer.validated_data['fact_name']:
            fact_name = serializer.validated_data['fact_name']
            active_project = Project.objects.get(id=self.kwargs['project_pk'])
            # retrieve tags with sufficient counts & create queries to build models
            tags = self.get_tags(fact_name,
                                 active_project,
                                 min_count=serializer.validated_data['min_fact_doc_count'],
                                 max_count=serializer.validated_data['max_fact_doc_count'])
            # check if found any tags to build models on
            if not tags:
                return Response({'error': f'found no tags for fact name: {fact_name}'}, status=status.HTTP_400_BAD_REQUEST)


            queries = json.dumps(self.create_queries(fact_name, tags))
            self.perform_create(serializer, fact_values=json.dumps(tags), queries=queries)
        else:
            return Response({"error": "Tag name must be included!"}, status=status.HTTP_400_BAD_REQUEST)



        headers = self.get_success_headers(serializer.data)

        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        try:
            neurotagger_model_location = json.loads(instance.location)['model']
            tokenizer_model_location = json.loads(instance.location)['tokenizer_model']
            tokenizer_vocab_model_location = json.loads(instance.location)['tokenizer_vocab']
            for model in(
                        neurotagger_model_location,
                        tokenizer_model_location,
                        tokenizer_vocab_model_location,
                        instance.plot.path,
                        ):
                os.remove(model)
            return Response({"success": f'Neurotagger instance "{instance.description}" deleted, models and plots were removed'}, status=status.HTTP_204_NO_CONTENT)
        except:
            return Response({"warning": f'Neurotagger instance "{instance.description}" deleted, but models and plots were not removed'}, status=status.HTTP_204_NO_CONTENT)


    @action(detail=True, methods=['post'], serializer_class=NeuroTaggerTagTextSerializer)
    def tag_text(self, request, pk=None, project_pk=None):
        """Returns tags for input text."""
        serializer = NeuroTaggerTagTextSerializer(data=request.data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, serializer.validated_data['text'], input_type='text')
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['post'], serializer_class=NeuroTaggerTagDocumentSerializer)
    def tag_doc(self, request, pk=None, project_pk=None):
        """Returns tags for input document."""
        serializer = NeuroTaggerTagDocumentSerializer(data=request.data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, serializer.data['doc'], input_type='doc')
        return Response(tagger_response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_object, tagger_input, input_type='text'):
        tagger = model_cache.get_model(tagger_object)
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)

        classes = json.loads(self.get_object().fact_values)
        probabilities = list(tagger_result[0])
        threshold = 0.0000001
        tag_data = [{ 'tag': label, 'probability': probability } for label, probability in zip(classes, probabilities) if probability > threshold]
        tag_data = sorted(tag_data, key=lambda k: k['probability'], reverse=True)

        result = {'tags': tag_data }

        return result


    @action(detail=True, methods=['get'])
    def tag_random_doc(self, request, pk=None, project_pk=None):
        """Returns list of tags for a random document in Elasticsearch."""
        # get tagger object
        tagger_object = self.get_object()
        tagger_id = tagger_object.id
        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)
        # retrieve tagger fields
        tagger_fields = json.loads(tagger_object.fields)

        if not ElasticCore().check_if_indices_exist(tagger_object.project.indices):
            return Response({'error': f'One or more index from {list(tagger_object.project.indices)} do not exist'}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve random document
        random_doc = ElasticSearcher(indices=tagger_object.project.indices).random_documents(size=1)[0]
        # filter out correct fields from the document
        random_doc_filtered = {k:v for k,v in random_doc.items() if k in tagger_fields}
        # apply tagger
        tagger_response = self.apply_tagger(tagger_object, random_doc_filtered, input_type='doc')
        response = {"document": random_doc, "prediction": tagger_response}
        return Response(response, status=status.HTTP_200_OK)
