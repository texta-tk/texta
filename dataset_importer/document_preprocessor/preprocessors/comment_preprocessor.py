# -*- coding: utf-8 -*-

from dateutil import parser
import json


class CommentPreprocessor(object):
    """
    Converts comments to suitable format for ElasticSearch.
    """

    def __init__(self):
        self._name = 'comment_preprocessor'

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

        if not kwargs.get('comment_preprocessor_preprocessor_feature_names', None):
            # this is mostly for API requests as they might not have field data - apply to all in this case
            input_features = documents[0].keys()
        else:
            input_features = json.loads(kwargs['comment_preprocessor_preprocessor_feature_names'])

        for input_feature in input_features:
            try:
                input_feature = json.loads(input_feature)["path"]
            except:
                pass

            is_date = None

            for i,document in enumerate(documents):
                if input_feature not in document:
                    continue

                feature_text = document[input_feature]
                if is_date is None:
                    if not feature_text.isdigit():
                        is_date = self._is_date(feature_text)
                
                if is_date:
                    document[input_feature] = 'hour_{0} month_{1}'.format(self._get_hour(feature_text), self._get_month(feature_text))
                else:
                    document[input_feature] = self._clean_string(feature_text)
                
                # update doc in list
                documents[i] = document

        return {'documents': documents, 'meta': {}}

