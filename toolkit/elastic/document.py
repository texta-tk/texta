import json
from typing import List

from elasticsearch.helpers import bulk
from elasticsearch_dsl import Search

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.decorators import elastic_connection


class ElasticDocument:
    """
    Everything related to managing documents in Elasticsearch
    """


    def __init__(self, index):
        self.core = ElasticCore()
        self.index = index


    @staticmethod
    def remove_duplicate_facts(facts: List[dict]):
        if facts:
            set_of_jsons = {json.dumps(fact, sort_keys=True, ensure_ascii=False) for fact in facts}
            without_duplicates = [json.loads(unique_fact) for unique_fact in set_of_jsons]
            return without_duplicates
        else:
            return []


    def __does_fact_exist(self, fact: dict, existing_facts: List[dict]):
        existing = set_of_jsons = {json.dumps(d, sort_keys=True) for d in existing_facts}
        checking = json.dumps(fact, sort_keys=True)
        if checking in existing:
            return True
        else:
            return False


    @elastic_connection
    def add_fact(self, fact: dict, doc_ids: List):
        # Fetch the documents with the bulk function to get the facts,
        # and to validate that those ids also exist.
        documents = self.get_bulk(doc_ids=doc_ids, fields=["texta_facts"])

        for document in documents:
            # If there is no texta_facts field in the index, add it.
            if "texta_facts" not in document["_source"]:
                self.core.add_texta_facts_mapping(document["_index"], [document["_type"]])
                document["_source"]["texta_facts"] = [fact]
                self.update(index=document["_index"], doc_type=document["_type"], doc_id=document["_id"], doc=document["_source"])

            else:
                # Avoid sending duplicates.
                if self.__does_fact_exist(fact, document["_source"]["texta_facts"]):
                    pass
                else:
                    document["_source"]["texta_facts"].append(fact)
                    self.update(index=document["_index"], doc_type=document["_type"], doc_id=document["_id"], doc=document["_source"])

        return True


    @elastic_connection
    def get(self, doc_id, fields: List = None):
        """
        Retrieve document by ID.
        """
        s = Search(using=self.core.es, index=self.index)
        s = s.query("ids", values=[doc_id])
        s = s.source(fields)
        s = s[:1000]
        response = s.execute()
        if response:
            document = response[0]
            return {"_index": document.meta.index, "_id": document.meta.id, "_type": document.meta.doc_type, "_source": document.to_dict()}
        else:
            return None


    @elastic_connection
    def get_bulk(self, doc_ids: List[str], fields: List[str] = None, flatten: bool = False) -> List[dict]:
        """
        Retrieve full Elasticsearch documents by their ids that includes id, index,
        type and content information. For efficiency it's recommended to limit the returned
        fields as unneeded content consumes extra internet bandwidth.
        """
        s = Search(using=self.core.es, index=self.index)
        s = s.query("ids", values=doc_ids)
        s = s.source(fields)
        s = s[:10000]
        response = s.execute()
        if response:
            return [{"_index": document.meta.index, "_id": document.meta.id, "_type": document.meta.doc_type, "_source": self.core.flatten(document.to_dict()) if flatten else document.to_dict()} for document in response]
        else:
            return []


    @elastic_connection
    def update(self, index, doc_type, doc_id, doc):
        """
        Updates document in ES by ID.
        """
        return self.core.es.update(index=index, doc_type=doc_type, id=doc_id, body={"doc": doc}, refresh="wait_for")


    @elastic_connection
    def bulk_update(self, actions, refresh="wait_for", chunk_size=100):
        """
        Intermediary function to commit bulk updates.
        This function doesn't have actions processing because it's easier to use
        when it's index unaware. Actions should be processed when needed.

        Setting refresh to "wait_for" makes Python wait until the documents are actually indexed
        to avoid version conflicts.

        Args:
            chunk_size: How many documents should be sent per batch.
            refresh: Which behaviour to use for updating the index contents on a shard level.
            actions: List of dictionaries or its generator containing raw Elasticsearch documents along with
            a "doc" and "op_type" field that contains the fields that need updating. For ex:
            {"_id": 1234, "_index": "reddit", "_type": "reddit", "op_type": "update", "doc": {"texta_facts": []}}

        Returns: Elasticsearch response to the request.
        """
        return bulk(client=self.core.es, actions=actions, refresh=refresh, request_timeout=30, chunk_size=chunk_size)


    @elastic_connection
    def add(self, doc):
        """
        Adds document to ES.
        """
        return self.core.es.index(index=self.index, doc_type=self.index, body=doc, refresh='wait_for')


    @elastic_connection
    def bulk_add(self, docs, chunk_size=100, raise_on_error=True, stats_only=True):
        """ _type is deprecated in ES 6"""
        actions = [{"_index": self.index, "_type": self.index, "_source": doc} for doc in docs]
        return bulk(client=self.core.es, actions=actions, chunk_size=chunk_size, stats_only=stats_only, raise_on_error=raise_on_error)


    @elastic_connection
    def bulk_add_raw(self, actions, chunk_size=100, raise_on_error=True, stats_only=True):
        return bulk(client=self.core.es, actions=actions, chunk_size=chunk_size, stats_only=stats_only, raise_on_error=raise_on_error)


    @elastic_connection
    def delete(self, doc_id):
        """
        Removes given document from ES.
        """
        return self.core.es.delete(index=self.index, doc_type=self.index, id=doc_id)


    @elastic_connection
    def delete_by_query(self, query):
        """
        Removes given document from ES.
        """
        return self.core.es.delete_by_query(index=self.index, body=query)


    @elastic_connection
    def count(self):
        """
        Returns the document count for given indices.
        :return: integer
        """
        return self.core.es.count(index=self.index)["count"]
