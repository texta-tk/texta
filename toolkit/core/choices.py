# CHOICES FOR CORE APP
from toolkit.elastic.core import ElasticCore


def get_index_choices():
   return [(a, a) for a in ElasticCore().get_indices()]

