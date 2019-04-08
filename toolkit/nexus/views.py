from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response

from toolkit.nexus.serializers import EntitySerializer


class EntityViewSet(viewsets.ViewSet):
    """
    API endpoint that allows TEXTA models to be viewed or edited.
    """
    serializer_class = EntitySerializer

    def list(self, request):
        entity_list = [{"name": "foo", "value": "bar"}]

        from toolkit.elastic.aggregator import ElasticAggregator
        es_a = ElasticAggregator()
        es_a.aggregate()


        serializer = EntitySerializer(
            instance=entity_list, many=True)
        return Response(serializer.data)        
