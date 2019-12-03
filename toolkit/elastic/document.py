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

    def get(self, doc_id):
        """
        Retrieve document by ID.
        """
        try:
            return self.core.es.get(index=self.index, doc_type=self.index, id=doc_id)["_source"]
        except:
            return None

    def update(self, doc_id, doc):
        """
        Updates document in ES by ID.
        """
        try:
            return self.core.es.update(index=self.index, doc_type=self.index, id=doc_id, body={"doc": doc})
        except:
            return None

    def add(self, doc):
        """
        Adds document to ES.
        """
        return self.core.es.index(index=self.index, doc_type=self.index, body=doc)

    def bulk_add(self, docs, chunk_size=100):
        ''' _type is deprecated in ES 6'''
        actions = [{"_index": self.index, "_type": self.index, "_source": doc} for doc in docs]
        return bulk(client=self.core.es, actions=actions, chunk_size=chunk_size, stats_only=True)

    def delete(self, doc_id):
        """
        Removes given document from ES.
        """
        return self.core.es.delete(index=self.index, doc_type=self.index, id=doc_id)

    def delete_by_query(self, query):
        """
        Removes given document from ES.
        """
        return self.core.es.delete_by_query(index=self.index, body=query)

    def count(self):
        """
        Returns the document count for given indices.
        :return: integer
        """
        return self.core.es.count(index=self.index)["count"]
