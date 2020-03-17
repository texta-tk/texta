# CHOICES FOR CORE APP
from toolkit.elastic.core import ElasticCore

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

MATCH_CHOICES = (('word', 'word'),( 'phrase', 'phrase'), ('phrase_prefix', 'phrase_prefix'))
OPERATOR_CHOICES = (('must', 'must'), ('must_not', 'mut_not'), ('should', 'should'))

DEFAULT_SUGGESTION_LIMIT = 10
DEFAULT_VALUES_PER_NAME = 10

ENV_VARIABLE_CHOICES = (
    ('TEXTA_ES_URL', 'TEXTA_ES_URL'),
    ('TEXTA_MLP_URL', 'TEXTA_MLP_URL'),
    ('TEXTA_REDIS_URL', 'TEXTA_REDIS_URL'),
    ('TEXTA_ES_USER', 'TEXTA_ES_USER'),
    ('TEXTA_ES_PASSWORD', 'TEXTA_ES_PASSWORD')
)