import math


# Sklearn average functions
AVG_FUNCTIONS = ["binary", "micro", "macro", "samples", "weighted"]
AVG_CHOICES = [(c, c) for c in AVG_FUNCTIONS]

MULTILABEL_AVG_FUNCTIONS = ["micro", "macro", "samples", "weighted"]
BINARY_AVG_FUNCTIONS = ["binary", "micro", "macro", "weighted"]

# Default average function for multilabel/multiclass
DEFAULT_AVG_FUNCTION = "macro"

# Max number of fact values retrieved with facts aggregation
DEFAULT_MAX_AGGREGATION_SIZE = 10000

# Max number of classes to calculate the confusion matrix.
# If the number of classes exceeds the allowed limit,
# an empty matrix is returned
DEFAULT_MAX_CONFUSION_CLASSES = 20


# Default min and max count of a label to display its results
# in `filtered_average` and `individual_results`.
DEFAULT_MIN_COUNT = 1
DEFAULT_MAX_COUNT = math.inf

# Fields that can be used for ordering the results in
# `filtered_average` and `individual_results`
ORDERING_FIELDS = ["alphabetic", "count", "precision", "recall", "f1_score", "accuracy"]
ORDERING_FIELDS_CHOICES = [(c, c) for c in ORDERING_FIELDS]
DEFAULT_ORDER_BY_FIELD = "alphabetic"

# Order results in descending order?
DEFAULT_ORDER_DESC = False

# Metrics used
METRICS = ["precision", "recall", "f1_score", "accuracy"]

# Available keys for setting metric restrictions
METRIC_RESTRICTION_FIELDS = ["max_score", "min_score"]

# Number of docs returned in one scroll
DEFAULT_SCROLL_SIZE = 500
DEFAULT_ES_TIMEOUT = 10


# If enabled, individual results for each label
# are also calculated and saved during multilabel
# evaluation
DEFAULT_ADD_INDIVIDUAL_RESULTS = True
