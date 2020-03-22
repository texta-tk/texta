from texta_tagger.pipeline import get_pipeline_builder

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.aggregator import ElasticAggregator

def get_field_choices():
   """
   Retrieves field options from ES.
   :return: list
   """
   es = ElasticCore()
   if es.connection:
      return [(a, '{0} - {1}'.format(a['index'], a['path'])) for a in es.get_fields()]
   else:
      return []

def get_classifier_choices():
   """
   Retrieves classifier choices.
   :return: list
   """
   pipeline = get_pipeline_builder()
   return [(a, a) for a in pipeline.get_classifier_options()]

def get_vectorizer_choices():
   """
   Retrieves vectorizer choices.
   :return: list
   """
   pipeline = get_pipeline_builder()
   return [(a, a) for a in pipeline.get_extractor_options()]


def get_feature_selector_choices():
   """
   Retrieves feature selector choices.
   :return: list
   """
   pipeline = get_pipeline_builder()
   return [(a, a) for a in pipeline.get_feature_selector_options()]


def get_tokenizer_choices():
   """
   Retrieves tokenizer choices
   :return: list
   """
   pipeline = get_pipeline_builder()
   return [(a, a) for a in pipeline.get_analyzer_options()]

DEFAULT_MAX_SAMPLE_SIZE = 10000
DEFAULT_NEGATIVE_MULTIPLIER = 1.0
DEFAULT_MIN_SAMPLE_SIZE = 50
DEFAULT_NUM_DOCUMENTS = 25
DEFAULT_NUM_CANDIDATES = 25
DEFAULT_TAGGER_GROUP_FACT_NAME = 'TEEMA'
DEFAULT_VECTORIZER = get_vectorizer_choices()[0][0]
DEFAULT_CLASSIFIER = get_classifier_choices()[0][0]
DEFAULT_FEATURE_SELECTOR = get_feature_selector_choices()[0][0]
DEFAULT_SCORE_THRESHOLD = 0.0