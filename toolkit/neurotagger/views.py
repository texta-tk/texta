from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.query import Query

from toolkit.neurotagger.models import Neurotagger
from toolkit.core.project.models import Project
from toolkit.neurotagger.serializers import NeurotaggerSerializer
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
from toolkit.tools.model_cache import ModelCache
from toolkit import permissions as toolkit_permissions
from toolkit.core import permissions as core_permissions
from toolkit.tagger.serializers import TextSerializer, DocSerializer

import json

# initialize model cache for neurotaggers
model_cache = ModelCache(NeurotaggerWorker)


def get_payload(request):
    if request.GET:
        data = request.GET
    elif request.POST:

        data = request.POST
    else:
        data = {}
    return data

class NeurotaggerViewSet(viewsets.ModelViewSet):
    serializer_class = NeurotaggerSerializer
    permission_classes = (core_permissions.ProjectResourceAllowed, permissions.IsAuthenticated)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user, 
                        project=Project.objects.get(id=self.kwargs['project_pk']),
                        fields=json.dumps(serializer.validated_data['fields']))

    def get_queryset(self):
        return Neurotagger.objects.filter(project=self.kwargs['project_pk'])


    def create(self, request, *args, **kwargs):
        serializer = NeurotaggerSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
    

    @action(detail=True, methods=['get','post'], serializer_class=TextSerializer)
    def tag_text(self, request, pk=None):
        """
        API endpoint for tagging raw text.
        """
        data = get_payload(request)
        serializer = TextSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger_id = tagger_object.pk
        tagger_response = self.apply_tagger(tagger_id, serializer.data['text'], input_type='text')
        return Response(tagger_response, status=status.HTTP_200_OK)


    @action(detail=True, methods=['get','post'], serializer_class=DocSerializer)
    def tag_doc(self, request, pk=None):
        """
        API endpoint for tagging JSON documents.
        """
        data = get_payload(request)
        serializer = DocSerializer(data=data)

        # check if valid request
        if not serializer.is_valid():
            return Response({'error': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        # retrieve tagger object
        tagger_object = self.get_object()

        # check if tagger exists
        if not tagger_object.location:
            return Response({'error': 'model does not exist (yet?)'}, status=status.HTTP_400_BAD_REQUEST)

        # check if fields match
        field_data = [ElasticCore().decode_field_data(field) for field in tagger_object.fields]
        field_path_list = [field['field_path'] for field in field_data]
        if set(field_path_list) != set(serializer.validated_data['doc'].keys()):
            return Response({'error': 'document fields do not match. Required keys: {}'.format(field_path_list)}, status=status.HTTP_400_BAD_REQUEST)

        # apply tagger
        tagger_id = tagger_object.pk
        tagger_response = self.apply_tagger(tagger_id, serializer.data['doc'], input_type='doc')
        return Response(tagger_response, status=status.HTTP_200_OK)


    def apply_tagger(self, tagger_id, tagger_input, input_type='text'):
        tagger = model_cache.get_model(tagger_id)
        if input_type == 'doc':
            tagger_result = tagger.tag_doc(tagger_input)
        else:
            tagger_result = tagger.tag_text(tagger_input)
        return {'result': bool(tagger_result[0]), 'probability': tagger_result[1]}
