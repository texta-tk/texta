import os

from toolkit.settings import BASE_DIR

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
    from toolkit.embedding.views import w2v_cache
    from toolkit.embedding.views import phraser_cache

    return {'w2v': len(w2v_cache.models.keys()),
            'phraser': len(phraser_cache.models.keys()),
            'tagger': len(tagger_cache.models.keys())}
