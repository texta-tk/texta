# CHOICES FOR EMBEDDING APP
from toolkit.elastic.core import ElasticCore

def get_field_choices():
   es = ElasticCore()
   return [(es.encode_field_data(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in es.get_fields()]

EMBEDDING_CHOICES = {"num_dimensions": [(100, 100), (200, 200), (300, 300)],
                         "max_vocab": [(0, 0), (50000, 50000), (100000, 100000), (500000, 500000), (1000000, 1000000)],
                         "min_freq": [(5, 5), (10, 10), (50, 50), (100, 100)],
           }