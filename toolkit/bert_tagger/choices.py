from toolkit.helper_functions import get_downloaded_bert_models
from toolkit.settings import BERT_PRETRAINED_MODEL_DIRECTORY

DOWNLOADED_BERT_MODELS = get_downloaded_bert_models(BERT_PRETRAINED_MODEL_DIRECTORY)

def get_default_bert_model(default_model: str = "bert-base-multilingual-cased") -> str:
    """ If defaulted model is downloaded, allow it; otherwise use the first model
        in downloaded models list as default.
    """
    if default_model in DOWNLOADED_BERT_MODELS or not DOWNLOADED_BERT_MODELS:
        return default_model
    else:
        return DOWNLOADED_BERT_MODELS[0]


DEFAULT_MAX_SAMPLE_SIZE = 100000
DEFAULT_MIN_SAMPLE_SIZE = 50
DEFAULT_NEGATIVE_MULTIPLIER = 1
DEFAULT_NUM_EPOCHS = 2
DEFAULT_TRAINING_SPLIT = 0.8
DEFAULT_LEARNING_RATE = 2e-5
DEFAULT_EPS = 1e-8
DEFAULT_MAX_LENGTH = 64
DEFAULT_BATCH_SIZE = 32
DEFAULT_BERT_MODEL = get_default_bert_model("bert-base-multilingual-cased")
DEFAULT_NEGATIVE_MULTIPLIER = 1.0
DEFAULT_REPORT_IGNORE_FIELDS = ["true_positive_rate", "false_positive_rate"]
DEFAULT_SKLEARN_AVG_BINARY = "binary"
DEFAULT_SKLEARN_AVG_MULTICLASS = "micro"
DEFAULT_AUTOADJUST_BATCH_SIZE = True
DEFAULT_USE_GPU = True
DEFAULT_ALLOW_STANDARD_OUTPUT = False

DEFAULT_BALANCE = False
DEFAULT_USE_SENTENCE_SHUFFLE = False
DEFAULT_BALANCE_TO_MAX_LIMIT = False
