from texta_elastic.core import ElasticCore


'''For storing constant variables'''
# Default max description lenght for models
MAX_DESC_LEN = 1000


def get_field_choices():
    """
    Retrieves field options from ES.
    """
    es = ElasticCore()
    if es.connection:
        return [(a, '{0} - {1}'.format(a['index'], a['path'])) for a in es.get_fields()]
    else:
        return []
