from .text_rnn.model import TextRNN
from .text_rnn.config import Config as TextRNNConfig

from .fasttext.model import fastText
from .fasttext.config import Config as fastTextConfig

from .rcnn.model import RCNN
from .rcnn.config import Config as RCNNConfig


#class TorchModel:



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