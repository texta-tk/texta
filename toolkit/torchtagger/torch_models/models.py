from .fasttext.config import Config as fastTextConfig
from .fasttext.model import fastText
from .rcnn.config import Config as RCNNConfig
from .rcnn.model import RCNN
from .text_rnn.config import Config as TextRNNConfig
from .text_rnn.model import TextRNN


TORCH_MODELS = {
    "TextRNN": {
        "model": TextRNN,
        "config": TextRNNConfig
    },
    "fastText": {
        "model": fastText,
        "config": fastTextConfig
    },
    "RCNN": {
        "model": RCNN,
        "config": RCNNConfig
    }
}
