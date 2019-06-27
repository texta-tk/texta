# CHOICES FOR TAGGER APP
from toolkit.elastic.core import ElasticCore
from toolkit.tagger.pipeline import get_pipeline_builder

def get_field_choices():
   es = ElasticCore()
   if es.connection:
      return sorted([(es.encode_field_data(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in es.get_fields()])
   else:
      return []


# TODO: implement this!
def get_fact_names():
    return [('TEEMA', 'TEEMA')]


def get_classifier_choices():
    pipeline = get_pipeline_builder()
    return [(a['index'], a['label']) for a in pipeline.get_classifier_options()]


def get_vectorizer_choices():
    pipeline = get_pipeline_builder()
    return [(a['index'], a['label']) for a in pipeline.get_extractor_options()]


DEFAULT_MAX_SAMPLE_SIZE = 10000
DEFAULT_NEGATIVE_MULTIPLIER = 1.0
DEFAULT_MIN_SAMPLE_SIZE = 50
DEFAULT_NUM_CANDIDATES = 25
