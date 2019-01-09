# -*- coding: utf-8 -*-

import logging
import requests
import logging
import json

from django.conf import settings


class MlpPreprocessor(object):
    """Preprocessor implementation for running TEXTA Multilingual Processor (MLP) on the selected documents.
    """

    def __init__(self, mlp_url=None, enabled_features=['text', 'lang', 'texta_facts']):
        """
        :param mlp_url: full URL to the MLP instance. Must be accessible.
        :param enabled_features: defines which MLP output features to list in the output documents. Is not used currently.
        :type mlp_url: string
        :type enabled_features: list of strings
        """
        self._mlp_url = mlp_url
        self._enabled_features = set(enabled_features)

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
            data = {'texts': json.dumps(texts, ensure_ascii=False), 'doc_path': 'mlp_' + input_feature}

            try:
                texts = [document[input_feature].decode() for document in documents if input_feature in document]
            except AttributeError:
                texts = [document[input_feature] for document in documents if input_feature in document]

            data = {'texts': json.dumps(texts, ensure_ascii=False), 'doc_path': input_feature+'_mlp'}

            try:
                analyzation_data = requests.post(self._mlp_url, data=data).json()
            except Exception:

                logging.error('Failed to achieve connection with mlp.', extra={'mlp_url':self._mlp_url, 'enabled_features':self._enabled_features})
                break

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                analyzation_datum = analyzation_datum[0]

                documents[analyzation_idx][input_feature+'_mlp'] = analyzation_datum['text']
                documents[analyzation_idx][input_feature+'_mlp']['lang'] = analyzation_datum['text']['lang']

                if 'texta_facts' not in documents[analyzation_idx]:
                    documents[analyzation_idx]['texta_facts'] = []

                documents[analyzation_idx]['texta_facts'].extend(analyzation_datum['texta_facts'])

        return {'documents': documents, 'meta': {}}


if __name__ == '__main__':
    mlp_processor = MlpPreprocessor(settings.DATASET_IMPORTER['urls'])
    docs = [{'text': u'Mina olen väga ilus.'}, {'text': u'Little cute donkey watched as little girl ate.'}]
    mlp_processor.transform(docs, **{'feature_map': {'text': 'tekst', 'lang': 'keel'}})

    print(docs)
