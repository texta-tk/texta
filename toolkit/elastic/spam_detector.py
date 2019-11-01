from typing import List

import elasticsearch
from elasticsearch_dsl import A, Q, Search
from elasticsearch_dsl.response import Response


class SpamDetector:

    def __init__(self, es_url: str, indices: List[str]):
        self.es = elasticsearch.Elasticsearch(es_url, timeout=60)
        self.indices = indices
        self.filtered_field_types = ["date", "fact"]


    def filter_fields(self, relevant_field_paths: List[str], all_field_info: List[dict]) -> List[dict]:
        without_wrong_types = list(filter(lambda x: x["type"] not in self.filtered_field_types, all_field_info))
        only_relevant_fields = list(filter(lambda x: x["path"] in relevant_field_paths, without_wrong_types))
        return only_relevant_fields


    def format_elastic_response(self, response: Response):
        ignored_keys = ["doc_count", "key"]
        container = []

        for hit in response.aggs.date_filter.spam.buckets:
            coocurrances = []
            frequent_texts = {"value": hit.key, "count": hit.doc_count}
            for field_name in dir(hit):
                if field_name not in ignored_keys:
                    occurance = getattr(hit, field_name)
                    for agg in occurance.buckets:
                        coocurrances.append({"value": agg.key, "count": agg.doc_count, "field": field_name})

            container.append({**frequent_texts, "occurances": coocurrances})

        return container


    def get_spam_content(self, target_field: str, common_feature_fields: List[dict], from_date: str = "now-1h", to_date: str = "now", date_field: str = "@timestamp", aggregation_size: int = 100, min_doc_count=10):
        s = Search(using=self.es, index=self.indices)
        s = s.extra(size=0)  # returns only aggregations, skips hits.

        date_filter = A("filter", Q("range", **{date_field: {'gte': from_date, 'lte': to_date}}))  # You need a filter aggregation to limit the documents of other aggregations.
        term_filter = A("terms", field="{}.keyword".format(target_field), size=aggregation_size, min_doc_count=min_doc_count)  # Frequent items aggregation to find posts with the same values.
        s.aggs.bucket("date_filter", date_filter).bucket("spam", term_filter)  # Applying the previous two pre-made aggregations into the query.

        # Nesting multiple frequent item aggregations into the "spam" frequent items aggregations.
        # Uses all the preset fields.
        for field in common_feature_fields:
            if field["type"] == "text":
                elastic_field_name = "{}.keyword".format(field["path"])
                s.aggs["date_filter"]["spam"].bucket(field["path"], "terms", field=elastic_field_name, size=aggregation_size, min_doc_count=min_doc_count)
            else:
                elastic_field_name = "{}".format(field["path"])
                s.aggs["date_filter"]["spam"].bucket(field["path"], "terms", field=elastic_field_name, size=aggregation_size, min_doc_count=min_doc_count)

        response = s.execute()

        return response
