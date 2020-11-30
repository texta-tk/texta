import logging
import os
from urllib.parse import urlparse

import redis
from celery.task.control import inspect
from rest_framework import exceptions

from toolkit.elastic.core import ElasticCore
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


def get_elastic_status(ES_URL=get_core_setting("TEXTA_ES_URL")):
    """
    Checks Elasticsearch connection status and version.
    """
    es_info = {"url": ES_URL, "alive": False}
    try:
        es_core = ElasticCore(ES_URL=ES_URL)
        if es_core.connection:
            es_info["alive"] = True
            es_info["status"] = es_core.es.info()
        return es_info
    except exceptions.ValidationError:
        return es_info


def get_redis_status():
    """
    Checks status of Redis server.
    """
    try:
        parser = urlparse(BROKER_URL)
        r = redis.Redis(host=parser.hostname, port=parser.port, socket_timeout=3)
        info = r.info()
        redis_status = {
            "alive": True,
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
