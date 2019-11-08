import os
import requests
from toolkit.settings import BASE_DIR, MLP_URL, ES_URL
from toolkit.elastic.core import ElasticCore
from toolkit.core.task.models import Task
from datetime import datetime, timedelta, time

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


def get_cache_status():
    """
    Gets info about model caches in applications.
    """
    from toolkit.tagger.tagger_views import global_tagger_cache
    from toolkit.embedding.views import global_w2v_cache, global_phraser_cache, global_cluster_cache


    return {'embedding': len(global_w2v_cache.models.keys()),
            'embedding_cluster': len(global_cluster_cache.models.keys()),
            'phraser': len(global_phraser_cache.models.keys()),
            'tagger': len(global_tagger_cache.models.keys())}


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
    Gets the number of active tasks by the last update and excludes inactive statuses
    """
    # 1 hour ago from now
    timeframe = datetime.now().date() - timedelta(hours=1)
    # Return the count of tasks with last update within an hour and exclude inactive status tasks
    return Task.objects.filter(last_update__gte=timeframe).exclude(
        status__in=[Task.STATUS_COMPLETED, Task.STATUS_CANCELLED, Task.STATUS_FAILED]
    ).count()
