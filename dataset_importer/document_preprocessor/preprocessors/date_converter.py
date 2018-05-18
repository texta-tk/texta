# -*- coding: utf-8 -*-

import dateutil.parser
import re

class DatePreprocessor(object):
    """
    Converts date fields to suitable format for ElasticSearch.
    """

    def __init__(self):
        self._months = {'jaanuar':'January',
                  'veebruar':'February',
                  'märts':'March',
                  'aprill':'April',
                  'mai':'May',
                  'juuni':'June',
                  'juuli':'July',
                  'august':'August',
                  'september':'September',
                  'oktoober':'October',
                  'november':'November',
                  'detsember':'December'}
                  
        self._est_months = '|'.join(self._months.keys())
        
        self._est_month_pattern = re.compile(self._est_months)
        self._date_pattern = re.compile('\d{4}-\d{2}-\d{2}')
        
        def _convert_month(self,date_val):
          '''
          Converts month names from estonian to english
          '''
          try:
              date_val = date_val.lower()
              est_month_matches = self._est_month_pattern.findall(date_val)
              for est_month in est_month_matches:
                date_val = re.sub(est_month,self._months[est_month],date_val)
          except Exception as e:
              print(e)
          return date_val
          
        def convert_date(self,date_val):
          '''
          Converts given date field value to standard ES format 
          yyyy-mm-dd
          
          params:
              o date_val - raw date field value
          '''
          try:
              d = self._convert_month(date_val)
              d = dateutil.parser.parse(d)
              d = str(d)
              
              date_matches = self._date_pattern.findall(d)
              date_match = date_matches[0] if date_matches else None
          except Exception as e:
              print(e)
              date_match = None
          return date_match

if __name__ == '__main__':
    pass
