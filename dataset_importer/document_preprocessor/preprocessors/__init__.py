"""preprocessors package contains specific document preprocessor implementations.

List here the new document preprocessors.
"""
import os
import sys

file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

from .comment_preprocessor import CommentPreprocessor
from .date_converter import DatePreprocessor
from .mlp import MlpPreprocessor
from .text_tagger import TextTaggerPreprocessor

__all__ = ["CommentPreprocessor",
           "DatePreprocessor",
           "MlpPreprocessor",
           "TextTaggerPreprocessor"]
