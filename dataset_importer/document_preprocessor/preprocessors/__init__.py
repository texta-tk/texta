"""preprocessors package contains specific document preprocessor implementations.

List here the new document preprocessors.
"""
# import os, sys
# file_dir = os.path.dirname(__file__)
# sys.path.append(file_dir)

# try:
#     import mlp
#     import date_converter
#     import text_tagger
# except Exception as e:
#     print(e)

from .text_tagger import TextTaggerPreprocessor
from .mlp import MlpPreprocessor
from .date_converter import DatePreprocessor


__all__ = ["TextTaggerPreprocessor",
           "MlpPreprocessor",
           "DatePreprocessor"]
