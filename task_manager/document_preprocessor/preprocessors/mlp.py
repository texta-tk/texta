# -*- coding: utf-8 -*-

import json
import logging

from texta.settings import ERROR_LOGGER
from utils.mlp_task_adapter import MLPTaskAdapter, Helpers


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

            feature_path = input_feature.split(".")
            if len(feature_path) > 1:
                texts = [Helpers.traverse_nested_dict_by_keys(document, feature_path) for document in documents]
            else:
                texts = [document[input_feature] if input_feature in document else "" for document in documents]

            data = {'texts': json.dumps(texts, ensure_ascii=False), 'doc_path': input_feature + '_mlp'}
            analyzation_data, errors = MLPTaskAdapter(self._mlp_url, mlp_type='mlp').process(data)

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                # This part is under a try catch because it's an notorious trouble maker.
                try:
                    analyzation_datum = analyzation_datum[0]

                    input_feature_path = input_feature.split(".")
                    if len(input_feature) == 1:
                        documents[analyzation_idx][input_feature + '_mlp'] = analyzation_datum['text']
                        documents[analyzation_idx][input_feature + '_mlp']['lang'] = analyzation_datum['text']['lang']
                        if 'texta_facts' not in documents[analyzation_idx]:
                            documents[analyzation_idx]['texta_facts'] = []
                        documents[analyzation_idx]['texta_facts'].extend(analyzation_datum['texta_facts'])

                    else:
                        # Make sure the last field is used as the path.
                        mlp_field_path = input_feature_path[:-1] + [input_feature_path[-1] + "_mlp"]
                        Helpers.set_in_dict(documents[analyzation_idx], mlp_field_path, analyzation_datum['text'])

                        lang_path = mlp_field_path + ["lang"]
                        Helpers.set_in_dict(documents[analyzation_idx], lang_path, analyzation_datum['text']['lang'])

                        if 'texta_facts' not in documents[analyzation_idx]:
                            documents[analyzation_idx]["texta_facts"] = []

                        documents[analyzation_idx]["texta_facts"].extend(analyzation_datum["texta_facts"])

                except Exception as e:
                    logging.getLogger(ERROR_LOGGER).exception("Error: {}, Document ID: {}".format(e, documents[analyzation_idx]))
                    continue

        return {'documents': documents, 'meta': {}, 'errors': errors}
