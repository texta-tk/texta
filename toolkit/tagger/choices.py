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


TAGGER_GROUP_CHOICES = {"min_freq": [(50,50), (100, 100), (250, 250), (500, 500), (1000, 1000), (3000, 3000), (5000, 5000), (10000, 10000)]}


TAGGER_CHOICES = {
                    "negative_multiplier": [(1.0, 1.0), (0.5, 0.5), (0.75, 0.75), (1.5, 1.5), (2.0, 2.0)],
                    "max_sample_size": [(10000, 10000), (25000, 25000), (50000, 50000), (100000, 100000)]
                }
