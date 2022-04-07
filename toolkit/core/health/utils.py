import logging
import os
from urllib.parse import urlparse

import redis
import torch
from celery.task.control import inspect
from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetMemoryInfo, nvmlInit
from rest_framework import exceptions
from texta_elastic.core import ElasticCore
from texta_elastic.exceptions import NotFoundError

from toolkit.helper_functions import get_core_setting
from toolkit.settings import BASE_DIR, BROKER_URL, ERROR_LOGGER


def get_version():
    """
    Imports version number from file system.
    :return: version as string.
    """
    try:
        with open(os.path.join(BASE_DIR, 'VERSION'), 'r') as fh:
            version = fh.read().strip()
    except IOError:
        version = 'unknown'
    return version


def reform_float_info(input_str):
    return float(input_str.replace("gb", "").replace("tb", "").replace("mb", ""))


def get_elastic_status(is_anon=False, uri=None):
    """
    Checks Elasticsearch connection status and version.
    """
    es_url = uri or get_core_setting("TEXTA_ES_URL")
    es_info = {"alive": False}
    try:
        es_core = ElasticCore(ES_URL=es_url)
        if es_core.connection:
            es_info["alive"] = True
            if is_anon is False:
                es_info["url"] = es_url
                es_info["status"] = es_core.es.info()
                es_info["disk"] = []
                for node in es_core.es.cat.allocation(format="json"):
                    # ignore unassigned nodes
                    if node["host"]:
                        node_info = {
                            "host": node["host"],
                            "free": reform_float_info(node["disk.avail"]),
                            "used": reform_float_info(node["disk.used"]),
                            "total": reform_float_info(node["disk.total"]),
                            "percent": reform_float_info(node["disk.percent"]),
                            "unit": "GB"
                        }
                        es_info["disk"].append(node_info)

        return es_info
    except exceptions.ValidationError:
        return es_info

    except NotFoundError:
        return es_info


def get_redis_status(is_anon: bool = False):
    """
    Checks status of Redis server.
    """
    try:
        parser = urlparse(BROKER_URL)
        r = redis.Redis(host=parser.hostname, port=parser.port, socket_timeout=3)
        info = r.info()
        redis_status = {"alive": True}

        if is_anon is False:
            redis_status = {
                **redis_status,
                "version": info["redis_version"],
                "expired_keys": info["expired_keys"],
                "used_memory": info["used_memory_human"],
                "total_memory": info["total_system_memory_human"]
            }

        return redis_status
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        return {
            "alive": False
        }


def get_active_tasks(is_redis_online):
    """
    Gets the number of active (running + queued) from message broker.
    """
    active_and_scheduled_tasks = 0
    if is_redis_online:
        inspector = inspect()

        active_tasks = inspector.active()
        scheduled_tasks = inspector.scheduled()
        if active_tasks:
            active_and_scheduled_tasks += sum([len(tasks) for tasks in active_tasks.values()])
        if scheduled_tasks:
            active_and_scheduled_tasks += sum([len(tasks) for tasks in scheduled_tasks.values()])
        return active_and_scheduled_tasks
    else:
        return active_and_scheduled_tasks


def get_gpu_memory(device_id: int):
    """
    Get GPU memory usage information.

    :param device_id: GPU's device id.
    """
    nvmlInit()
    h = nvmlDeviceGetHandleByIndex(device_id)
    info = nvmlDeviceGetMemoryInfo(h)

    total = info.total / (2 ** 30)
    free = info.free / (2 ** 30)
    used = info.used / (2 ** 30)

    unit = "GB"
    return {"total": total, "free": free, "used": used, "unit": unit}


def get_gpu_devices():
    """
    Get GPU devices with corresponding memory usage information.
    """
    gpu_count = torch.cuda.device_count()
    device_ids = [i for i in range(0, gpu_count)]

    devices = []
    for device_id in device_ids:
        memory = get_gpu_memory(device_id)
        new_device = {
            "id": device_id,
            "name": torch.cuda.get_device_name(),
            "memory": {
                "free": memory["free"],
                "total": memory["total"],
                "used": memory["used"],
                "unit": memory["unit"]
            }
        }
        devices.append(new_device)
    return devices
