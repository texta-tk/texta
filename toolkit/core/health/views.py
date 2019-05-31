from rest_framework import views, status
from rest_framework.response import Response

from toolkit.elastic.core import ElasticCore
from toolkit.core.health.utils import get_version, get_cache_status
import shutil
import psutil

class HealthView(views.APIView):

    def get(self, request):
        toolkit_status = {}
        toolkit_status['elastic_alive'] = ElasticCore().connection
        toolkit_status['api_version'] = get_version()

        disk_total, disk_used, disk_free = shutil.disk_usage("/")
        toolkit_status['disk'] = {'free': disk_free / (2**30), 
                                  'total': disk_total / (2**30),
                                  'used': disk_used / (2**30),
                                  'unit': 'GB'}
        
        memory = psutil.virtual_memory()
        toolkit_status['memory'] = {'free': memory.available / (2**30),
                                    'total': memory.total / (2**30),
                                    'used': memory.used / (2**30),
                                    'unit': 'GB'}
        
        toolkit_status['cpu'] = {'percent': psutil.cpu_percent()}
        toolkit_status['model_cache'] = get_cache_status()

        return Response(toolkit_status, status=status.HTTP_200_OK)
