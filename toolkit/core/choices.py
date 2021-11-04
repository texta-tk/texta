# CHOICES FOR CORE APP
from texta_elastic.core import ElasticCore
from toolkit.settings import CORE_SETTINGS

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

MATCH_CHOICES = (('word', 'word'), ('phrase', 'phrase'), ('phrase_prefix', 'phrase_prefix'))
OPERATOR_CHOICES = (('must', 'must'), ('must_not', 'mut_not'), ('should', 'should'))

OUTPUT_CHOICES = (('raw', 'raw'), ('doc_with_id', 'doc_with_id'))

DEFAULT_SUGGESTION_LIMIT = 10
DEFAULT_VALUES_PER_NAME = 10

CORE_VARIABLE_CHOICES = [(a, a) for a in CORE_SETTINGS.keys()]
