# CHOICES FOR CORE APP
from toolkit.elastic.elastic import Elastic


def get_index_choices():
   return [(a, a) for a in Elastic().get_indices()]

