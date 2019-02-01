from dateutil import parser
from time import sleep
import requests
import logging
import json

from utils.mlp_task_adapter import MLPTaskAdapter

class MLPLitePreprocessor(object):
    """
    Cleans texts for classification. Lemmatizes text.
    """

    def __init__(self, mlp_url=None):
        self.mlp_url = mlp_url

    @staticmethod
    def _process_stats(stats):
        """ Processes stats from TextCleaner to make them categorical
        """
        processed_stats = {}
        if stats:
            for stat_key, stat_val in stats.items():
                if isinstance(stat_val, list) and stat_key == 'obfuscated':
                    if stat_val:
                        processed_stats[stat_key] = 'obfuscated'
                    else:
                        processed_stats[stat_key] = 'not_obfuscated'
                if isinstance(stat_val, list):
                    processed_stats[stat_key] = ' '.join(stat_val)
                elif isinstance(stat_val, float):
                    processed_stats[stat_key] = str(stat_val).replace('.', '_')
                elif isinstance(stat_val, int):
                    processed_stats[stat_key] = str(len(str(stat_val)))
                else:
                    processed_stats[stat_key] = stat_val
        
        return processed_stats

    def transform(self, documents, **kwargs):
        """Takes input documents and creates new fields for further commentary analysis.
        :param documents: collection of dictionaries to enhance
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :return: enhanced documents
        :rtype: list of dicts
        """

        if not kwargs.get('text_cleaner_preprocessor_feature_names', None):
            # this is mostly for API requests as they might not have field data - apply to all in this case
            input_features = list(documents[0].keys())
        else:
            input_features = json.loads(kwargs['text_cleaner_preprocessor_feature_names'])

        for input_feature in input_features:
            try:
                input_feature = json.loads(input_feature)["path"]
            except:
                pass

            texts = [document[input_feature] for document in documents if input_feature in document]
            data = {'texts': json.dumps(texts, ensure_ascii=False)}

            analyzation_data, errors = MLPTaskAdapter(self.mlp_url, mlp_type='mlp_lite').process(data)

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                documents[analyzation_idx][input_feature+'_mlp-lite'] = {}
                documents[analyzation_idx][input_feature+'_mlp-lite']['text'] = analyzation_datum['text']
                documents[analyzation_idx][input_feature+'_mlp-lite']['stats'] = self._process_stats(analyzation_datum['stats'])

        return {'documents': documents, 'meta': {}, 'erros': errors}
