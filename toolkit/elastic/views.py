from rest_framework import views, status
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore


class ElasticGetIndices(views.APIView):
    """
    Retrieves all available Elasticsearch indices.
    """
    def get(self, request):
        es_core = ElasticCore()
        if not es_core.connection:
            return Response({"error": "no connection to Elasticsearch"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        indices = sorted(ElasticCore().get_indices())
        return Response(indices, status=status.HTTP_200_OK)
