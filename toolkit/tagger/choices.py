# CHOICES FOR TAGGER APP
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.tagger.pipeline import get_pipeline_builder

def get_field_choices():
   """
   Retrieves field options from ES.
   """
   es = ElasticCore()
   if es.connection:
      return sorted([(es.encode_field_data(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in es.get_fields()])
   else:
      return []


#def get_fact_names(indices=[]):
#   """
#   Retrieves fact names based on specific index.
#   """
#   es_a = ElasticAggregator(indices=indices)
#   fact_names = es_a.facts(include_values=False)
#   return [(a, a) for a in fact_names]


def get_classifier_choices():
   """
   Retrieves classifier choices.
   """
   pipeline = get_pipeline_builder()
   return [(a['index'], a['label']) for a in pipeline.get_classifier_options()]


def get_vectorizer_choices():
   """
   Retrieves vectorizer choices.
   """
   pipeline = get_pipeline_builder()
   return [(a['index'], a['label']) for a in pipeline.get_extractor_options()]


def get_feature_selector_choices():
   """
   Retrieves feature selector choices.
   """
   pipeline = get_pipeline_builder()
   return [(a['index'], a['label']) for a in pipeline.get_feature_selector_options()]


DEFAULT_MAX_SAMPLE_SIZE = 10000
DEFAULT_NEGATIVE_MULTIPLIER = 1.0
DEFAULT_MIN_SAMPLE_SIZE = 50
DEFAULT_NUM_CANDIDATES = 25
DEFAULT_TAGGER_GROUP_FACT_NAME = 'TEEMA'