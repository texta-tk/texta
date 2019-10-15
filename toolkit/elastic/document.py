import json
import uuid

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from toolkit.elastic.core import ElasticCore


class ElasticDocument:
    """
    Everything related to managing documents in Elasticsearch
    """

    def __init__(self, index):
        self.core = ElasticCore()
        self.index = index

    def add(self, doc):
        """
        Adds document to ES.
        """
        return self.core.es.index(index=self.index, doc_type=self.index, body=doc)

    def bulk_add(self, doc, index):
        # print(doc)
        ''' _type is deprecated in ES 6'''
        actions = [{"_index": index, "_type": "your doctype", "_id": uuid.uuid4(), "_source": doc}]
        return bulk(client=self.core.es, actions=actions, chunk_size=1000)

    def remove(self, doc_id):
        """
        Removes given document from ES.
        """
        return self.core.es.delete(index=self.index, doc_type=self.index, id=doc_id)

    def count(self):
        """
        Returns the document count for given indices.
        :return: integer
        """
        return self.core.es.count(index=self.index)["count"]
