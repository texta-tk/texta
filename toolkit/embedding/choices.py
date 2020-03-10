# CHOICES FOR EMBEDDING APP
from toolkit.elastic.core import ElasticCore

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
