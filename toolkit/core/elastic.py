from elasticsearch import Elasticsearch
import json

from toolkit.settings import ES_URL


class Elastic(object):
    
    def __init__(self):
        self.es = Elasticsearch([ES_URL])
        self.empty_query = json.dumps({"query": {}})
    
    def check_connection(self):
        if self.es.ping():
            return True
        else:
            return False

    def get_indices(self):
        if self.check_connection():
            return [(a, a) for i,a in enumerate(self.es.indices.get_alias('*').keys())]
        else:
            return []