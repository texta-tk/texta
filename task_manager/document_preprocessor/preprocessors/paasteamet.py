# -*- coding: utf-8 -*-


class PaasteametPreprocessor(object):
    """Preprocessor implementation for running topic extraction and sentiment analysis methods for Scoro's datasets.
    """

    def __init__(self, feature_map={}):
        self._feature_map = feature_map
        
    def transform(self, documents, **kwargs):
        return {"documents":documents, "meta": {}}
