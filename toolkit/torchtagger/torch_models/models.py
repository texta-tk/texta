from .text_cnn.model import TextCNN
from .text_cnn.config import Config as TextCNNConfig

from .fasttext.model import fastText
from .fasttext.config import Config as fastTextConfig

from .rcnn.model import RCNN
from .rcnn.config import Config as RCNNConfig


#class TorchModel:



TORCH_MODELS = {
    "TextCNN": {
        "model": TextCNN,
        "config": TextCNNConfig
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