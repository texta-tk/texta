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

# Max number of fact names returned while validating the existance of facts in an index
DEFAULT_MAX_FACT_AGGREGATION_SIZE = 5000

# Max number of classes to calculate the confusion matrix.
# If the number of classes exceeds the allowed limit,
# an empty matrix is returned
DEFAULT_MAX_CONFUSION_CLASSES = 70


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

# If true, apply token-based evaluation for entities; otherwise labelsets of documents are compared
# and results are calculated based on them
DEFAULT_TOKEN_BASED = True


# If true, example values of misclassified examples are stored along with partial overlaps
# (only for for entity evaluation)
DEFAULT_ADD_MISCLASSIFIED_EXAMPLES = True

# Limit the misclassified values stored in the data model
MAX_MISCLASSIFIED_VALUES_STORED = 1000

EVALUATION_TYPES = ["binary", "multilabel", "entity"]
EVALUATION_TYPE_CHOICES = [(et, et) for et in EVALUATION_TYPES]

# Key for evaluation type 'entity'
ENTITY_EVALUATION = "entity"

# Default min count for the misclassified examples returned by endpoint "misclassified_examples"
DEFAULT_MIN_MISCLASSIFIED_COUNT = 1

# Default max count of the misclassified examples returned by endpoint "misclassified_examples"
DEFAULT_MAX_MISCLASSIFIED_COUNT = 100000000

# Max number of misclassified examples to return per class
DEFAULT_N_MISCLASSIFIED_VALUES_TO_RETURN = 100

# Marker for scores containing devision by zero
SCORES_NAN_MARKER = -1

# Label used in the confusion matrix for predicted labels that are not present in true labels
MISSING_TRUE_LABEL = "Missing from true labels"

# Label used in the confusion matrix for true labels that are note present in predicted labels
MISSING_PRED_LABEL = "Missing from pred labels"
