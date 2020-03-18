from urllib.parse import urlparse
from celery.task.control import inspect
import requests
import redis
import os

from toolkit.elastic.core import ElasticCore
from toolkit.settings import BASE_DIR, BROKER_URL
from toolkit.helper_functions import get_core_setting


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


def get_mlp_status(MLP_URL=get_core_setting("TEXTA_MLP_URL")):
    """
    Checks if MLP is available.
    """
    mlp_info = {"url": MLP_URL, "alive": False}
    try:
        response = requests.get(MLP_URL, timeout=3)
        if response.status_code == 200:
            mlp_info["status"] = response.json()
            mlp_info["alive"] = True
    except Exception as e:
        return mlp_info
    return mlp_info


def get_elastic_status(ES_URL=get_core_setting("TEXTA_ES_URL")):
    """
    Checks Elasticsearch connection status and version.
    """
    es_info = {"url": ES_URL, "alive": False}
    es_core = ElasticCore(ES_URL=ES_URL)
    if es_core.connection:
        es_info["alive"] = True
        es_info["status"] = es_core.es.info()
    return es_info


def get_redis_status():
    """
    Checks status of Redis server.
    """
    try:
        parser = urlparse(BROKER_URL)
        r = redis.Redis(host=parser.hostname, port=parser.port)
        info = r.info()
        redis_status = {
            "alive": True,
            "version": info["redis_version"],
            "expired_keys": info["expired_keys"],
            "used_memory": info["used_memory_human"],
            "total_memory": info["total_system_memory_human"]
        }
        return redis_status
    except redis.exceptions.ConnectionError:
        return {
            "alive": False
        }


def get_active_tasks():
    """
    Gets the number of active (running + queued) from message broker.
    """
    active_and_scheduled_tasks = 0
    inspector = inspect()

    active_tasks = inspector.active()
    scheduled_tasks = inspector.scheduled()
    if active_tasks:
        active_and_scheduled_tasks += sum([len(tasks) for tasks in active_tasks.values()])
    if scheduled_tasks:
        active_and_scheduled_tasks += sum([len(tasks) for tasks in scheduled_tasks.values()])
    return active_and_scheduled_tasks
