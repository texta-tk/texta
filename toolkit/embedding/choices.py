# CHOICES FOR EMBEDDING APP
from texta_elastic.core import ElasticCore
from toolkit.elastic.tools.data_sample import ES6_SNOWBALL_MAPPING, ES7_SNOWBALL_MAPPING


def get_field_choices():
    es = ElasticCore()
    if es.connection:
        return [(a, '{0} - {1}'.format(a['index'], a['path'])) for a in es.get_fields()]
    else:
        return []


DEFAULT_MAX_DOCUMENTS = 0
DEFAULT_NUM_DIMENSIONS = 100
DEFAULT_MIN_FREQ = 5
DEFAULT_MAX_VOCAB = 50000
DEFAULT_OUTPUT_SIZE = 10

W2V_EMBEDDING = "W2VEmbedding"
FASTTEXT_EMBEDDING = "FastTextEmbedding"

EMBEDDING_CHOICES = [(a, a) for a in [W2V_EMBEDDING, FASTTEXT_EMBEDDING]]
