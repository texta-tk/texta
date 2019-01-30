from dateutil import parser
import requests
import logging
import json

from texta.settings import mlp_url

# derive url from mlp url
text_cleaner_url = mlp_url.replace('/mlp/process', '/text_cleaner/process')

class TextCleanerPreprocessor(object):
    """
    Cleans texts for classification. Lemmatizes text.
    """

    def __init__(self):
        pass

    @classmethod
    def _is_date(cls, string):
        try:
            parser.parse(string)
            return True
        except ValueError:
            return False

    @classmethod
    def _get_hour(cls, string):
        try:
            return str(parser.parse(string).hour)
        except ValueError:
            return ''

    @classmethod
    def _get_month(cls, string):
        try:
            return str(parser.parse(string).month)
        except ValueError:
            return ''

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

            try:
                texts = [document[input_feature].decode() for document in documents if input_feature in document]
            except AttributeError:
                texts = [document[input_feature] for document in documents if input_feature in document]

            data = {'texts': json.dumps(texts, ensure_ascii=False)}

            try:
                analyzation_data = requests.post(text_cleaner_url, data=data).json()
            except Exception:
                logging.error('Failed to achieve connection with mlp.', extra={'mlp_url':text_cleaner_url})
                break

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                documents[analyzation_idx][input_feature+'_clean'] = {}
                documents[analyzation_idx][input_feature+'_clean']['text'] = analyzation_datum['text']
                documents[analyzation_idx][input_feature+'_clean']['stats'] = self._process_stats(analyzation_datum['stats'])

        return {'documents': documents, 'meta': {}}
        