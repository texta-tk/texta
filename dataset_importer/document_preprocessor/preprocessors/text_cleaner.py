from dateutil import parser
import requests
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

    @classmethod
    def _clean_string(cls, string):
        return string.strip().lower()

    def transform(self, documents, **kwargs):
        """Takes input documents and creates new fields for further commentary analysis.

        :param documents: collection of dictionaries to enhance
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :return: enhanced documents
        :rtype: list of dicts
        """

        print(kwargs)

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

            #print(texts)

            data = {'texts': json.dumps(texts, ensure_ascii=False)}

            try:
                analyzation_data = requests.post(text_cleaner_url, data=data).json()
            except Exception:
                #logging.error('Failed to achieve connection with mlp.', extra={'mlp_url':self._text_cleaner_url, 'enabled_features':self._enabled_features})
                break

            #print(analyzation_data)

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                analyzation_datum = analyzation_datum[0]

                documents[analyzation_idx][input_feature+'_clean'] = analyzation_datum['text']
                documents[analyzation_idx][input_feature+'_stats'] = analyzation_datum['stats']
        
        print(documents[0])

        return {'documents': documents, 'meta': {}}

