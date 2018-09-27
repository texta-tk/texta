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
        """Takes input documents and enhances them with MLP output.

        :param documents: collection of dictionaries to enhance
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :return: enhanced documents
        :rtype: list of dicts
        """

        if not kwargs.get('comment_preprocessor_preprocessor_feature_names', None):
            return documents

        input_features = json.loads(kwargs['comment_preprocessor_preprocessor_feature_names'])

        for input_feature in input_features:
            month_label = '%s_month_comment_preprocessor' % input_feature
            hour_label = '%s_hour_comment_preprocessor' % input_feature
            label = '%s_comment_preprocessor' % input_feature
            is_date = None
            for document in documents:
                if input_feature not in document:
                    continue

                feature_text = document[input_feature]
                if is_date is None:
                    if not feature_text.isdigit():
                        is_date = self._is_date(feature_text)

                if is_date:
                    document.update({
                        month_label: self._get_month(feature_text),
                        hour_label: self._get_hour(feature_text)
                    })
                else:
                    document.update({label: self._clean_string(feature_text)})

        return {'documents': documents, 'meta': {}}

