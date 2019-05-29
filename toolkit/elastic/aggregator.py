import json

from toolkit.elastic.core import ElasticCore
from toolkit.settings import ES_URL

class ElasticAggregator:
    """
    Everything related to performing aggregations in Elasticsearch
    """
    EMPTY_QUERY = {"query": {"match_all": {}}}

    def __init__(self, field_data=[], indices=[], query=EMPTY_QUERY):
        self.core = ElasticCore()
        self.field_data = self.core.parse_field_data(field_data)
        self.indices = self._load_indices(indices)
        self.query = query
    

    def _load_indices(self, indices):
        # load from field data or indices list
        if not indices:
            return ",".join([field["index"] for field in self.field_data])
        else:
            return indices


    def update_query(self, query):
        self.query = query


    def update_field_data(self, field_data):
        self.field_data = self.core.parse_field_data(field_data)


    def _aggregate(self, agg_query):
        self.query["aggregations"] = agg_query
        response = self.core.es.search(index=self.indices, body=self.query)
        return response


    def facts(self, size=30, filter_by_fact_name=None, min_count=0, include_values=True):
        """
        For retrieving entities (facts) from ES
        """
        agg_query = {"facts": {
                            "nested": {"path": "texta_facts"},
                            "aggs": {
                                "facts": {
                                    "terms": {"field": "texta_facts.fact", "size": size}
                                }
                            }
                        }
                    }

        # filter by name if fact name present
        if filter_by_fact_name:
            agg_query["facts"]["aggs"]["facts"]["terms"]["include"] = [filter_by_fact_name]

        if include_values:
            agg_query["facts"]["aggs"]["facts"]["aggs"] = {"fact_values": {"terms": {"field": "texta_facts.str_val", "size": size}}}

        response = self._aggregate(agg_query)
        
        fact_names = response["aggregations"]["facts"]["facts"]["buckets"]
        entities = {}
        for fact_type in fact_names:
            fact_name = fact_type["key"]
            entities[fact_name] = []
            if "fact_values" in fact_type:
                for fact_value in fact_type["fact_values"]["buckets"]:
                    if fact_value["key"] and fact_value["doc_count"] > min_count:
                        entities[fact_name].append(fact_value["key"])
        
        # filter by name if fact name present
        if filter_by_fact_name:
            if filter_by_fact_name in entities:
                entities = entities[filter_by_fact_name]
            else:
                entities = []

        if not include_values:
            entities = list(entities.keys())
        
        return entities