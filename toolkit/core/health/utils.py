import os

import requests
from celery.task.control import inspect

from toolkit.elastic.core import ElasticCore
from toolkit.settings import BASE_DIR, ES_URL, MLP_URL


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


def get_mlp_status():
    """
    Checks if MLP is available.
    """
    mlp_info = {"url": MLP_URL, "alive": False}

    try:
        response = requests.get(MLP_URL)
        if response.status_code == 200:
            mlp_info["status"] = response.json()
            mlp_info["alive"] = True
    except:
        pass

    return mlp_info


def get_elastic_status():
    """
    Checks Elasticsearch connection status and version.
    """
    es_info = {"url": ES_URL, "alive": False}
    es_core = ElasticCore()

    if es_core.connection:
        es_info["alive"] = True
        es_info["status"] = es_core.es.info()

    return es_info


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
