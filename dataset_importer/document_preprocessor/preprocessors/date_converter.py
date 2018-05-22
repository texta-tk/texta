# -*- coding: utf-8 -*-

import dateparser
import re
#from dateparser.search import search_dates


class DatePreprocessor(object):
    """
    Converts date fields to suitable format for ElasticSearch.
    """
    
    def __init__(self):
        self._languages = ['et','en','ru']
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
      :param kwargs: request parameters which must include entries for the 
                     preprocessors to work appropriately
      :type date_field_value: string
      :return: date converted to standard ES format
      :rtype: string
      '''
      
      # TODO: 
      '''
      if not kwargs.get('mlp_preprocessor_input_features', None):
        kwargs['mlp_preprocessor_input_features'] = '["text"]'
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
  
    def extract_dates(self,text,convert=False):
        dates = re.findall(self._date_pattern,text)
        if convert:
            dates = [self.convert_date(d) for d in dates]
        return dates

      

'''
if __name__ == '__main__':
    pass
'''

dp = DatePreprocessor()

text = u' bla 03. juuni 2018 blablabla 02.03.2009 blabla'

text_2 = '02.03.2009'
dates = dp.extract_dates(text,convert=True)
print dates



