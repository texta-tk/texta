import psutil
import shutil
from keras import backend as K
from rest_framework import views, status
from rest_framework.response import Response

from toolkit.core.health.utils import get_version, get_cache_status, get_mlp_status, get_elastic_status

class HealthView(views.APIView):

    def get(self, request):
        toolkit_status = {}

        toolkit_status['elastic'] = get_elastic_status()

        toolkit_status['mlp_version'] = get_mlp_status()
        toolkit_status['version'] = get_version()

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
        
        gpus = K.tensorflow_backend._get_available_gpus()
        toolkit_status['gpu'] = {'count': len(gpus), 'devices': gpus}

        return Response(toolkit_status, status=status.HTTP_200_OK)
