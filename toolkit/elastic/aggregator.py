from typing import List

from elasticsearch_dsl import A, Q, Search

from toolkit.elastic.core import ElasticCore


class ElasticAggregator:
    """
    Everything related to performing aggregations in Elasticsearch
    """
    EMPTY_QUERY = {"query": {"match_all": {}}}


    def __init__(self, field_data=[], indices=[], query=EMPTY_QUERY):
        """
        field_data: list of decoded fields
        indices: list of index names (strings)
        """
        self.core = ElasticCore()
        self.field_data = field_data
        self.indices = indices
        self.query = query


    def update_query(self, query):
        self.query = query


    def update_field_data(self, field_data):
        """
        Updates field data. Expects list of decoded fields.
        """
        self.field_data = field_data


    def _aggregate(self, agg_query):
        self.query["aggregations"] = agg_query
        response = self.core.es.search(index=self.indices, body=self.query)
        return response


    def get_spam_content(self, target_field: str, all_fields: List[dict], from_date: str = "now-1h", to_date: str = "now", date_field: str = "@timestamp", aggregation_size: int = 100, min_doc_count=10):
        s = Search(using=self.core.es, index=self.indices)

        date_filter = A("filter", Q("range", **{date_field: {'gte': from_date, 'lte': to_date}}))
        term_filter = A("terms", field="{}.keyword".format(target_field), size=aggregation_size, min_doc_count=min_doc_count)

        s.aggs.bucket("date_filter", date_filter).bucket("spam", term_filter)
        s = s.extra(size=0)  # returns only aggregations, skips hits.

        for field in all_fields:
            ignored_fields = ["date", "fact"]
            if field["type"] not in ignored_fields:
                if field["type"] == "text":
                    s.aggs["date_filter"]["spam"].bucket(field, "terms", field="{}.keyword".format(field), size=aggregation_size, min_doc_count=min_doc_count)
                else:
                    s.aggs["date_filter"]["spam"].bucket(field, "terms", field="{}".format(field), size=aggregation_size, min_doc_count=min_doc_count)

        response = s.execute().to_dict()
        return response


    def facts(self, size=30, filter_by_fact_name=None, min_count=0, max_count=None, include_values=True):
        """
        For retrieving entities (facts) from ES
        """
        agg_query = {
            "facts": {
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
        aggregations = response["aggregations"]
        entities = {}

        if aggregations["facts"]["doc_count"] > 0:
            fact_names = aggregations["facts"]["facts"]["buckets"]
            for fact_type in fact_names:
                fact_name = fact_type["key"]
                entities[fact_name] = []
                if "fact_values" in fact_type:
                    for fact_value in fact_type["fact_values"]["buckets"]:
                        if fact_value["key"] and fact_value["doc_count"] > min_count:
                            if max_count:
                                if fact_value["doc_count"] < max_count:
                                    entities[fact_name].append(fact_value["key"])
                            else:
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
