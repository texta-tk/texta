from texta_tagger.pipeline import get_pipeline_builder

from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.choices import get_snowball_choices

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


def get_scoring_choices():
    """
    Retrieves scoring choices.
    :return: list
    """
    scoring_choices = ["default", "precision", "recall", "f1_score", "accuracy", "jaccard"]
    return [(a, a) for a in scoring_choices]

DEFAULT_VECTORIZER = get_vectorizer_choices()[0][0]
DEFAULT_CLASSIFIER = get_classifier_choices()[0][0]
DEFAULT_SNOWBALL_LANGUAGE = get_snowball_choices()[0][0]

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
DEFAULT_SCORING_OPTIONS = get_scoring_choices()
DEFAULT_SCORING_FUNCTION = get_scoring_choices()[0][0]



DEFAULT_ES_TIMEOUT = 10
DEFAULT_BULK_SIZE = 100
DEFAULT_MAX_CHUNK_BYTES = 104857600
