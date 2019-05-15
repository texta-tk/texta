from rest_framework import views, status
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.core.health.utils import get_version

class HealthView(views.APIView):

    def get(self, request):
        toolkit_status = {}
        toolkit_status['elastic_alive'] = ElasticCore().connection
        toolkit_status['api_version'] = get_version()

        return Response(toolkit_status, status=status.HTTP_200_OK)
