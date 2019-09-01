import os
import requests
from toolkit.settings import BASE_DIR, MLP_URL, ES_URL
from toolkit.elastic.core import ElasticCore

def get_version():
    """
    Imports version number from file system.
    :return: version as string.
    """
    try:
        with open(os.path.join(BASE_DIR, 'VERSION'), 'r') as fh:
            version = fh.read()
    except IOError:
        version = 'unknown'
    return version


def get_cache_status():
    """
    Gets info about model caches in applications.
    """
    from toolkit.tagger.views import model_cache as tagger_cache
    from toolkit.embedding.views import w2v_cache, phraser_cache, cluster_cache


    return {'embedding': len(w2v_cache.models.keys()),
            'embedding_cluster': len(cluster_cache.models.keys()),
            'phraser': len(phraser_cache.models.keys()),
            'tagger': len(tagger_cache.models.keys())}


def get_mlp_status():
    """
    Checks if MLP is available.
    """
    try:
        response = requests.get(MLP_URL)
        if response.status_code == 200:
            return response.json()['version']
    except:
        return None


def get_elastic_status():
    """
    Checks Elasticsearch connection status and version.
    """
    es_info = {"url": ES_URL, "alive": False}
    es_core = ElasticCore()

    if es_core.connection:
        es_info["alive"] = True
        es_info["cluster_info"] = es_core.es.info()

    return es_info


