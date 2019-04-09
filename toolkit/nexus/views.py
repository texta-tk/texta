from django.shortcuts import render
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from toolkit.nexus.serializers import EntitySerializer


class EntityViewSet(viewsets.ViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    serializer_class = EntitySerializer

    def list(self, request, project_pk=None):
        from toolkit.elastic.aggregator import ElasticAggregator
        es_a = ElasticAggregator()
        entities = es_a.entities(include_values=False)
        return Response(entities)

    @action(detail=True, methods=['get', 'post'])
    def predict(self, request, pk=None, project_pk=None):
        data = self.get_payload(request)
        #serializer = PredictionSerializer(data=data)
        #if serializer.is_valid():
        #    data = serializer.data