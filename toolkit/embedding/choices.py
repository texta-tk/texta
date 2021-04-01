# CHOICES FOR EMBEDDING APP
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.choices import get_snowball_choices

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

EMBEDDING_CHOICES = [(a,a) for a in [W2V_EMBEDDING, FASTTEXT_EMBEDDING]]

DEFAULT_SNOWBALL_LANGUAGE = get_snowball_choices()[0][0]
