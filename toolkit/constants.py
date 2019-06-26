from toolkit.elastic.core import ElasticCore

'''For storing constant variables'''
# Default max description lenght for models
MAX_DESC_LEN = 100

def get_field_choices():
   es = ElasticCore()
   if es.connection:
      return sorted([(es.encode_field_data(a), '{0} - {1}'.format(a['index'], a['field']['path'])) for a in es.get_fields()])
   else:
      return []
