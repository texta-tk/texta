import json
from typing import List

from elasticsearch.helpers import bulk
from elasticsearch_dsl import Search

from toolkit.elastic.core import ElasticCore


class ElasticDocument:
    """
    Everything related to managing documents in Elasticsearch
    """


    def __init__(self, index):
        self.core = ElasticCore()
        self.index = index


    def __remove_duplicate_facts(self, facts: List[dict]):
        set_of_jsons = {json.dumps(d, sort_keys=True) for d in facts}  # set-comprehension
        without_duplicates = [json.loads(fact) for fact in set_of_jsons]
        return without_duplicates


    def __does_fact_exist(self, fact: dict, existing_facts: List[dict]):
        existing = set_of_jsons = {json.dumps(d, sort_keys=True) for d in existing_facts}
        checking = json.dumps(fact, sort_keys=True)
        if checking in existing:
            return True
        else:
            return False


    def add_fact(self, fact: dict, doc_ids: List):
        # Fetch the documents with the bulk function to get the facts,
        # and to validate that those ids also exist.
        documents = self.get_bulk(doc_ids=doc_ids, fields=["texta_facts"])

        for document in documents:
            # If there is no texta_facts field in the index, add it.
            if "texta_facts" not in document["_source"]:
                self.core.add_texta_facts_mapping(document["_index"], document["_type"])
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


    def get_bulk(self, doc_ids: List[str], fields: List[str] = None) -> List[dict]:
        """
        Retrieve full Elasticsearch documents by their ids that includes id, index,
        type and content information. For efficiency it's recommended to limit the returned
        fields as unneeded content consumes extra internet bandwidth.
        """
        s = Search(using=self.core.es, index=self.index)
        s = s.query("ids", values=doc_ids)
        s = s.source(fields)
        s = s[:1000]
        response = s.execute()
        if response:
            return [{"_index": document.meta.index, "_id": document.meta.id, "_type": document.meta.doc_type, "_source": document.to_dict()} for document in response]
        else:
            return []


    def update(self, index, doc_type, doc_id, doc):
        """
        Updates document in ES by ID.
        """
        return self.core.es.update(index=index, doc_type=doc_type, id=doc_id, body={"doc": doc}, refresh="wait_for")


    def add(self, doc):
        """
        Adds document to ES.
        """
        return self.core.es.index(index=self.index, doc_type=self.index, body=doc, refresh='wait_for')


    def bulk_add(self, docs, chunk_size=100):
        """ _type is deprecated in ES 6"""
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
