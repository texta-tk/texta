import json

from toolkit.elastic.core import ElasticCore
from toolkit.settings import ES_URL

class ElasticAggregator:
    """
    Everything related to performing aggregations in Elasticsearch
    """
    EMPTY_QUERY = {"query": {"match_all": {}}}

    def __init__(self, field_data=[], query=EMPTY_QUERY):
        self.core = ElasticCore()
        self.field_data = self.core.parse_field_data(field_data)
        self.indices = ",".join([field["index"] for field in field_data])
        self.query = query
    

    def _aggregate(self, agg_query):
        self.query["aggregations"] = agg_query
        response = self.core.es.search(index=self.indices, body=self.query)
        return response
    

    def entities(self, size=30, include_values=True):
        agg_query = {"facts": {
                            "nested": {"path": "texta_facts"},
                            "aggs": {
                                "facts": {
                                    "terms": {"field": "texta_facts.fact", "size": size}
                                }
                            }
                        }
                    }
        if include_values:
            agg_query["facts"]["aggs"]["facts"]["aggs"] = {"fact_values": {"terms": {"field": "texta_facts.str_val", "size": size}}}

        response = self._aggregate(agg_query)
        fact_names = response["aggregations"]["facts"]["facts"]["buckets"]
        entities = {}
        print(fact_names)
        for fact_type in fact_names:
            fact_name = fact_type["key"]
            entities[fact_name] = []
            if "fact_values" in fact_type:
                for fact_value in fact_type["fact_values"]["buckets"]:
                    entities[fact_name].append(fact_value["key"])
        if not include_values:
            entities = list(entities.keys())
        return entities