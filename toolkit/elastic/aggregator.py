import json

from toolkit.elastic.core import ElasticCore
from toolkit.settings import ES_URL

class ElasticAggregator:
    """
    Everything related to performing aggregations in Elasticsearch
    """
    EMPTY_QUERY     = {"query": {"match_all": {}}}

    def __init__(self, field_data=[], query=EMPTY_QUERY):
        self.core = ElasticCore()
        self.field_data = self.core.parse_field_data(field_data)
        self.indices = ','.join([field['index'] for field in field_data])
        self.query = query
    

    def aggregate(self):
        response = self.core.es.search(index=self.indices, body=self.query)
        print(response.keys())