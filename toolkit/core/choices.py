# CHOICES FOR CORE APP
from texta_elastic.core import ElasticCore
from texta_elastic.settings import ALLOWED_KEY_FIELDS, ALLOWED_VALUE_FIELDS
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

DEFAULT_INCLUDE_DOC_PATH = False
DEFAULT_INCLUDE_VALUES = True
DEFAULT_EXCLUDE_ZERO_SPANS = False
DEFAULT_FACT_NAME = ""
DEFAULT_MLP_DOC_PATH = ""

DEFAULT_MAX_AGGREGATION_COUNT = 30
DEFAULT_FILTER_BY_KEY = ""

KEY_FIELD_CHOICES = [(c, c) for c in ALLOWED_KEY_FIELDS]
VALUE_FIELD_CHOICES = [(c, c) for c in ALLOWED_VALUE_FIELDS]

CORE_VARIABLE_CHOICES = [(a, a) for a in CORE_SETTINGS.keys()]
