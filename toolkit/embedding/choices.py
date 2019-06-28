# CHOICES FOR EMBEDDING APP
from toolkit.elastic.core import ElasticCore

def get_field_choices():
   es = ElasticCore()
   if es.connection:
      return [(es.encode_field_data(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in es.get_fields()]
   else:
      return []


DEFAULT_NUM_DIMENSIONS = 100
DEFAULT_MIN_FREQ = 5
DEFAULT_MAX_VOCAB = 50000
DEFAULT_OUTPUT_SIZE = 10

DEFAULT_NUM_CLUSTERS = 500
DEFAULT_BROWSER_NUM_CLUSTERS = 50
DEFAULT_BROWSER_EXAMPLES_PER_CLUSTER = 10
