# -*- coding: utf-8 -*-

import dateparser
import re
import json

class DatePreprocessor(object):
    """
    Converts date fields to suitable format for ElasticSearch.
    """
    
    def __init__(self):
        self._languages = ['et']#,'en','ru']
        self._date_pattern = self._get_date_patterns()
        
    def _get_date_patterns(self):
        
        '''
        Compiles common date patterns for date extraction
        '''
        dp_1 = '(?<=\D)\d{1,2}\.\s*\d{1,2}\.\s*\d{1,4}(?=$|\D)'  # 02.05.2018
        dp_2 = '(?<=\D)\d{1,2}\.\s*[a-züõöä]+\s*\d{2,4}(?=$|\D)' # 2. mai 2018
        dps = dp_1 + '|' + dp_2
        pattern = re.compile(dps)
        return pattern
    
    def set_languages(self,langs):
        '''
        Set default languages for parsing dates
        '''
        self._languages = langs
              
    def convert_date(self,date_field_value,langs=[]):#, **kwargs):
      '''Converts given date field value to standard ES format yyyy-mm-dd
      
      :param date_field_value: date field value to convert
      :param langs: language(s) of the data (optional)
      :type date_field_value: string
      :type langs: list
      :return: date converted to standard ES format
      :rtype: string
      '''
     
      if langs:
          self._languages = langs
      try:
          datetime_object = dateparser.parse(date_field_value,languages=self._languages)
          formatted_date = datetime_object.strftime('%Y-%m-%d')

      except Exception as e:
          print(e)
          formatted_date = None
      return formatted_date
  
    def convert_batch(self, date_batch,langs=[]):
      '''Converts given date batch to standard ES format yyyy-mm-dd
      
      :param date_batch: date batch to convert
      :param langs: language(s) of the data (optional)

      :type date_batch: list
      :type langs: list
      :return: dates converted to standard ES format
      :rtype: list
      '''
      converted_batch = [self.convert_date(date,langs=langs) for date in date_batch]
      return converted_batch
      
      
  
    def extract_dates(self,text,convert=False):
        '''Extracts dates from given text
        
        :param text: plaintext containing date values
        :param convert: whether to convert extracted date data to es standard or not
        :type text: string
        :type convert: boolean
        :return: extracted dates
        :rtype: list
        '''
        
        dates = re.findall(self._date_pattern,text)
        if convert:
            dates = [self.convert_date(d) for d in dates]
        return dates
    
    def transform(self, documents, **kwargs):
        '''Takes input documents and enhances them with MLP output.

        :param documents: collection of dictionaries to enhance
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :return: enhanced documents
        :rtype: list of dicts
        '''

        if not kwargs.get('date_converter_preprocessor_input_features', None):
            return documents

        input_features = json.loads(kwargs['date_converter_preprocessor_input_features'])

        if kwargs.get('date_converter_preprocessor_input_langs',None):
            input_langs = json.loads(kwargs['date_converter_preprocessor_input_langs'])
            
            # TODO: Check validity of language codes
            if input_langs[0] and len(input_langs)==2:
                self._languages = input_langs


        for input_feature in input_features:
            raw_dates = [document[input_feature] for document in documents if input_feature in document]
            try:
                converted_dates = self.convert_batch(raw_dates)
            except:
                converted_dates = []
                raise Exception()

            for analyzation_idx, analyzation_datum in enumerate(converted_dates):
                documents[analyzation_idx][input_feature+'_converted'] = analyzation_datum
                '''
                if 'texta_facts' not in documents[analyzation_idx]:
                    documents[analyzation_idx]['texta_facts'] = []

                documents[analyzation_idx]['texta_facts'].extend(analyzation_datum['texta_facts'])'''

        return documents

