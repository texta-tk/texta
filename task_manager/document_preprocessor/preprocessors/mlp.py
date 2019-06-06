# -*- coding: utf-8 -*-

import logging
import requests
from requests.exceptions import ConnectionError, Timeout
import logging
import json

from utils.mlp_task_adapter import MLPTaskAdapter


class MlpPreprocessor(object):
    """Preprocessor implementation for running TEXTA Multilingual Processor (MLP) on the selected documents.
    """

    def _reload_env(self):
        import dotenv
        dotenv.load_dotenv(".env")

    def __init__(self, mlp_url=None, enabled_features=['text', 'lang', 'texta_facts']):
        """
        :param mlp_url: full URL to the MLP instance. Must be accessible.
        :param enabled_features: defines which MLP output features to list in the output documents. Is not used currently.
        :type mlp_url: string
        :type enabled_features: list of strings
        """
        self._mlp_url = mlp_url
        self._enabled_features = set(enabled_features)
        self._reload_env()

    def transform(self, documents, **kwargs):
        """Takes input documents and enhances them with MLP output.

        :param documents: collection of dictionaries to enhance
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :return: enhanced documents
        :rtype: list of dicts
        """
        if not self._enabled_features:
            return documents

        if not kwargs.get('mlp_feature_names', None):
            kwargs['mlp_feature_names'] = '["text"]'

        input_features = json.loads(kwargs['mlp_feature_names'])

        for input_feature in input_features:

            texts = [document[input_feature] for document in documents if input_feature in document]
            data = {'texts': json.dumps(texts, ensure_ascii=False), 'doc_path': input_feature+'_mlp'}

            analyzation_data, errors = MLPTaskAdapter(self._mlp_url, mlp_type='mlp').process(data)

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                analyzation_datum = analyzation_datum[0]
                documents[analyzation_idx][input_feature+'_mlp'] = analyzation_datum['text']
                documents[analyzation_idx][input_feature+'_mlp']['lang'] = analyzation_datum['text']['lang']
                if 'texta_facts' not in documents[analyzation_idx]:
                    documents[analyzation_idx]['texta_facts'] = []
                documents[analyzation_idx]['texta_facts'].extend(analyzation_datum['texta_facts'])

        return {'documents': documents, 'meta': {}, 'errors': errors}
