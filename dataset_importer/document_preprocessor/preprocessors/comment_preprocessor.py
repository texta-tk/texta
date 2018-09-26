# -*- coding: utf-8 -*-
import logging

from dateutil.parser import parse
import re
import json


def is_date(string):
    try:
        parse(string)
        return True
    except ValueError:
        return False


class CommentPreprocessor(object):
    """
    Converts comments to suitable format for ElasticSearch.
    """
    
    def __init__(self):
        self._languages = ['et']

    # def _get_date_patterns(self):
    #     """
    #     Compiles common date patterns for date extraction
    #     """
    #     dp_1 = '(?<=\D)\d{1,2}\.\s*\d{1,2}\.\s*\d{1,4}(?=$|\D)'  # 02.05.2018
    #     dp_2 = '(?<=\D)\d{1,2}\.\s*[a-züõöä]+\s*\d{2,4}(?=$|\D)' # 2. mai 2018
    #     dps = dp_1 + '|' + dp_2
    #     pattern = re.compile(dps)
    #     return pattern
    #
    # def set_languages(self,langs):
    #     '''
    #     Set default languages for parsing dates
    #     '''
    #     self._languages = langs
    #
    # def convert_date(self,date_field_value,langs=[]):#, **kwargs):
    #     '''Converts given date field value to standard ES format yyyy-mm-dd
    #
    #     :param date_field_value: date field value to convert
    #     :param langs: language(s) of the data (optional)
    #     :type date_field_value: string
    #     :type langs: list
    #     :return: date converted to standard ES format
    #     :rtype: string
    #     '''
    #
    #     if langs:
    #         self._languages = langs
    #     try:
    #         if self._languages:
    #             datetime_object = dateparser.parse(date_field_value,languages=self._languages)
    #             # If fails to parse with given language (returns None)
    #             if not datetime_object:
    #                 datetime_object = dateparser.parse(date_field_value)
    #         else:
    #             datetime_object = dateparser.parse(date_field_value)
    #
    #         if datetime_object:
    #             formatted_date = datetime_object.strftime('%Y-%m-%d')
    #
    #     except Exception as e:
    #         print(e)
    #         formatted_date = None
    #     return formatted_date
    #
    # def convert_batch(self, date_batch, langs=[]):
    #     """Converts given date batch to standard ES format yyyy-mm-dd
    #
    #     :param date_batch: date batch to convert
    #     :param langs: language(s) of the data (optional)
    #
    #     :type date_batch: list
    #     :type langs: list
    #     :return: dates converted to standard ES format
    #     :rtype: list
    #     """
    #
    #     converted_batch = [self.convert_date(date,langs=langs) for date in date_batch]
    #     return converted_batch
    #
    #
    #
    # def extract_dates(self,text,convert=False):
    #     """Extracts dates from given text
    #
    #     :param text: plaintext containing date values
    #     :param convert: whether to convert extracted date data to es standard or not
    #     :type text: string
    #     :type convert: boolean
    #     :return: extracted dates
    #     :rtype: list
    #     """
    #
    #     dates = re.findall(self._date_pattern, text)
    #     if convert:
    #         dates = [self.convert_date(d) for d in dates]
    #     return dates
    
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
            texts = []
            for document in documents:
                if input_feature in document:
                    texts.append(document[input_feature])

            # TODO: implement actual preprocessing here
            preprocessed_texts = [t + '_preprocessed' for t in texts]

            label = '%s_comment_preprocessor' % input_feature
            for i, preprocessed in enumerate(preprocessed_texts):
                documents[i][label] = preprocessed

        return {'documents': documents, 'meta': {}}

