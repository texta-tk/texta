from .neuro_models import NeuroModels

DEFAULT_SEQ_LEN = 50
DEFAULT_VOCAB_SIZE = 50000
DEFAULT_NUM_EPOCHS = 5
DEFAULT_VALIDATION_SPLIT = 0.2

DEFAULT_MAX_SAMPLE_SIZE = 10000
DEFAULT_NEGATIVE_MULTIPLIER = 1.0
DEFAULT_SCORE_THRESHOLD = 0.0

# For choicefield
model_arch_choices = (
    (NeuroModels.FNN, NeuroModels.FNN),
    (NeuroModels.CNN, NeuroModels.CNN),
    (NeuroModels.GRU, NeuroModels.GRU),
    (NeuroModels.LSTM, NeuroModels.LSTM),
    (NeuroModels.GRUCNN, NeuroModels.GRUCNN),
    (NeuroModels.LSTMCNN, NeuroModels.LSTMCNN)
)
