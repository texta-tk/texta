import json
import logging
from typing import List

import elasticsearch
from elasticsearch.helpers import bulk
from elasticsearch_dsl import Q, Search

from toolkit.elastic.core import ElasticCore
from toolkit.elastic.decorators import elastic_connection
from toolkit.settings import ERROR_LOGGER


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
        existing = {json.dumps(d, sort_keys=True) for d in existing_facts}
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
                self.core.add_texta_facts_mapping(document["_index"])
                document["_source"]["texta_facts"] = [fact]
                doc_type = document.get("_type", "_doc")
                self.update(index=document["_index"], doc_type=doc_type, doc_id=document["_id"], doc=document["_source"])

            else:
                # Avoid sending duplicates.
                if self.__does_fact_exist(fact, document["_source"]["texta_facts"]):
                    pass
                else:
                    document["_source"]["texta_facts"].append(fact)
                    doc_type = document.get("_type", "_doc")
                    self.update(index=document["_index"], doc_type=doc_type, doc_id=document["_id"], doc=document["_source"])

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
            doc_type = getattr(document.meta, "doc_type", "_doc")
            return {"_index": document.meta.index, "_type": doc_type, "_id": document.meta.id, "_source": document.to_dict()}
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
            container = []
            for document in response:
                document = {
                    "_index": document.meta.index,
                    "_type": getattr(document.meta, "doc_type", "_doc"),
                    "_id": document.meta.id,
                    "_source": self.core.flatten(document.to_dict()) if flatten else document.to_dict()
                }
                container.append(document)
            return container
        else:
            return []


    @elastic_connection
    def update(self, index, doc_id, doc, doc_type="_doc", retry_on_conflict=1):
        """
        Updates document in ES by ID.
        """
        return self.core.es.update(index=index, doc_type=doc_type, id=doc_id, body={"doc": doc}, refresh="wait_for", retry_on_conflict=retry_on_conflict)


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
            {"_id": 1234, "_index": "reddit", "op_type": "update", "doc": {"texta_facts": []}}

        Returns: Elasticsearch response to the request.
        """
        actions = self.add_type_to_docs(actions)
        return bulk(client=self.core.es, actions=actions, refresh=refresh, request_timeout=30, chunk_size=chunk_size)


    @elastic_connection
    def add(self, doc):
        """
        Adds document to ES.
        """
        return self.core.es.index(index=self.index, body=doc, refresh='wait_for')


    @elastic_connection
    def bulk_add(self, docs, chunk_size=100, raise_on_error=True, stats_only=True):
        actions = [{"_index": self.index, "_source": doc, "_type": doc.get("_type", "_doc")} for doc in docs]
        return bulk(client=self.core.es, actions=actions, chunk_size=chunk_size, stats_only=stats_only, raise_on_error=raise_on_error)


    def add_type_to_docs(self, actions):
        for action in actions:
            doc_type = action.get("_type", "_doc")
            action["_type"] = doc_type
            yield action


    @elastic_connection
    def bulk_add_generator(self, actions, chunk_size=100, raise_on_error=True, stats_only=True, refresh="wait_for"):
        actions = self.add_type_to_docs(actions)
        try:
            return bulk(client=self.core.es, actions=actions, chunk_size=chunk_size, stats_only=stats_only, raise_on_error=raise_on_error, refresh=refresh)
        except elasticsearch.helpers.errors.BulkIndexError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.args[1][0]['index']['error']['reason'], exc_info=False)
            return None


    @elastic_connection
    def delete(self, doc_id):
        """
        Removes given document from ES.
        """
        return self.core.es.delete(index=self.index, id=doc_id)


    @elastic_connection
    def delete_by_query(self, query):
        """
        Removes given document from ES.
        """
        return self.core.es.delete_by_query(index=self.index, body=query)


    @elastic_connection
    def bulk_delete(self, document_ids: List[str], wait_for_completion=True):
        query = Search().query(Q("ids", values=document_ids)).to_dict()
        response = self.core.es.delete_by_query(index=self.index, body=query, wait_for_completion=wait_for_completion)
        return response


    @elastic_connection
    def count(self, indices=None) -> int:
        """
        Returns the document count for given indices.
        :indices: Either a coma separated string of indices or a list of index strings.
        """
        index = indices if indices else self.index
        return self.core.es.count(index=index)["count"]
