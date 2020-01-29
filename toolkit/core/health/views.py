import shutil

import psutil
import torch
from rest_framework import views, status
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from toolkit.core.health.utils import get_active_tasks, get_elastic_status, get_mlp_status, get_version


@permission_classes((AllowAny,))
class HealthView(views.APIView):
    def get(self, request):
        """Returns health statistics about host machine and running services."""
        toolkit_status = {}

        toolkit_status['elastic'] = get_elastic_status()

        toolkit_status['mlp'] = get_mlp_status()
        toolkit_status['version'] = get_version()

        disk_total, disk_used, disk_free = shutil.disk_usage("/")
        toolkit_status['disk'] = {
            'free': disk_free / (2 ** 30),
            'total': disk_total / (2 ** 30),
            'used': disk_used / (2 ** 30),
            'unit': 'GB'
        }

        memory = psutil.virtual_memory()
        toolkit_status['memory'] = {
            'free': memory.available / (2 ** 30),
            'total': memory.total / (2 ** 30),
            'used': memory.used / (2 ** 30),
            'unit': 'GB'
        }

        toolkit_status['cpu'] = {'percent': psutil.cpu_percent()}

        gpu_count = torch.cuda.device_count()
        gpu_devices = [torch.cuda.get_device_name(i) for i in range(0, gpu_count)]

        toolkit_status['gpu'] = {'count': gpu_count, 'devices': gpu_devices}
        toolkit_status['active_tasks'] = get_active_tasks()

        return Response(toolkit_status, status=status.HTTP_200_OK)
