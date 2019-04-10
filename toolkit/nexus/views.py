from django.shortcuts import render
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.nexus.serializers import EntitySerializer
from toolkit.elastic.aggregator import ElasticAggregator


class EntityViewSet(viewsets.ViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    serializer_class = EntitySerializer

    def list(self, request, project_pk=None):
        es_a = ElasticAggregator()
        entities = es_a.entities(include_values=False)
        return Response(entities)

    def retrieve(self, request, pk=None, project_pk=None):
        es_a = ElasticAggregator()
        entities = es_a.entities(include_values=True)
        if pk not in entities:
            return Response({'error': 'unknown entity type'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(entities[pk])


    @action(detail=True, methods=['get', 'post'])
    def related(self, request, pk=None, project_pk=None):
        es_a = ElasticAggregator()
        entities = es_a.related_entities(include_values=True)

        print(pk)
        #serializer = PredictionSerializer(data=data)
        #if serializer.is_valid():
        #    data = serializer.data