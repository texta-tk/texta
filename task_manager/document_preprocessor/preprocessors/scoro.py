# -*- coding: utf-8 -*-

class ScoroPreprocessor(object):
    """Preprocessor implementation for running topic extraction and sentiment analysis methods for Scoro's datasets.
    """

    def __init__(self, feature_map={}):
        pass


    def transform(self, documents, **kwargs):
        return {"documents":documents, "meta": {}}
