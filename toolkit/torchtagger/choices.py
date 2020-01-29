from .torch_models.models import TORCH_MODELS

DEFAULT_MAX_SAMPLE_SIZE = 100000
DEFAULT_MIN_SAMPLE_SIZE = 50
DEFAULT_NEGATIVE_MULTIPLIER = 1
DEFAULT_NUM_EPOCHS = 5
DEFAULT_VALIDATION_SPLIT = 0.8

MODEL_CHOICES = [(a, a) for a in TORCH_MODELS.keys()]
