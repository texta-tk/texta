# CHOICES FOR TRAINER APP
from toolkit.elastic.core import ElasticCore
from toolkit.trainer.tagger.pipeline import get_pipeline_builder

def get_field_choices():
   es = ElasticCore()
   return [(es.encode_field_data(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in es.get_fields()]


def get_classifier_choices():
    pipeline = get_pipeline_builder()
    return [(a['index'], a['label']) for a in pipeline.get_classifier_options()]


def get_vectorizer_choices():
    pipeline = get_pipeline_builder()
    return [(a['index'], a['label']) for a in pipeline.get_extractor_options()]


MODEL_CHOICES = {"embedding": {"num_dimensions": [(100, 100), (200, 200), (300, 300)],
                         "max_vocab": [(0, 0), (50000, 50000), (100000, 100000), (500000, 500000), (1000000, 1000000)],
                         "min_freq": [(5, 5), (10, 10), (50, 50), (100, 100)],
                         },
           "tagger": {
               "negative_multiplier": [(1.0, 1.0), (0.5, 0.5), (1.5, 1.5), (2.0, 2.0)],
               "max_sample_size": [(10000, 10000), (25000, 25000), (50000, 50000), (100000, 100000)]
           },
           "extractor": {}
           }

STATUS_CREATED = 'created'
STATUS_QUEUED = 'queued'
STATUS_RUNNING = 'running'
STATUS_UPDATING = 'updating'
STATUS_COMPLETED = 'completed'
STATUS_CANCELED = 'canceled'
STATUS_FAILED = 'failed'

STATUS_CHOICES = (
    (STATUS_CREATED, 'Created'),
    (STATUS_QUEUED, 'Queued'),
    (STATUS_RUNNING, 'Running'),
    (STATUS_UPDATING, 'Updating'),
    (STATUS_COMPLETED, 'Completed'),
    (STATUS_CANCELED, 'Canceled'),
    (STATUS_FAILED, 'Failed'),
)
