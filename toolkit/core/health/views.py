import os
import shutil

import psutil
import torch
from rest_framework import status, views
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from toolkit.core.health.utils import (get_active_tasks, get_elastic_status, get_gpu_devices, get_redis_status, get_version)
from toolkit.settings import DEFAULT_MLP_LANGUAGE_CODES


@permission_classes((AllowAny,))
class HealthView(views.APIView):

    def get(self, request):
        """Returns health statistics about host machine and running services."""
        toolkit_status = {"services": {}, "host": {}, "toolkit": {}}
        is_anon = request.user.is_anonymous

        toolkit_status["services"]["elastic"] = get_elastic_status(is_anon)
        toolkit_status["services"]["redis"] = get_redis_status(is_anon)

        toolkit_status["toolkit"]["version"] = get_version()
        toolkit_status["toolkit"]["available_langs"] = DEFAULT_MLP_LANGUAGE_CODES

        if is_anon is True:
            toolkit_status.pop("host")
            toolkit_status["toolkit"].pop("available_langs")
            return Response(toolkit_status, status=status.HTTP_200_OK)

        disk_total, disk_used, disk_free = shutil.disk_usage("/")
        toolkit_status["host"]["disk"] = {
            "free": disk_free / (2 ** 30),
            "total": disk_total / (2 ** 30),
            "used": disk_used / (2 ** 30),
            "unit": "GB"
        }

        memory = psutil.virtual_memory()
        toolkit_status["host"]["memory"] = {
            "free": memory.available / (2 ** 30),
            "total": memory.total / (2 ** 30),
            "used": memory.used / (2 ** 30),
            "unit": "GB"
        }

        toolkit_status["host"]["cpu"] = {"percent": psutil.cpu_percent(), "count": os.cpu_count()}

        gpu_count = torch.cuda.device_count()
        gpu_devices = get_gpu_devices()

        toolkit_status["host"]["gpu"] = {"count": gpu_count, "devices": gpu_devices}
        toolkit_status["toolkit"]["active_tasks"] = get_active_tasks(toolkit_status["services"]["redis"]["alive"])

        return Response(toolkit_status, status=status.HTTP_200_OK)
