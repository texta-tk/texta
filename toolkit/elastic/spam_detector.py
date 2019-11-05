from typing import List

import elasticsearch
from elasticsearch_dsl import A, Q, Search


class SpamDetector:
    FILTERED_FIELD_TYPES = ["date", "fact"]


    def __init__(self, es_url: str, indices: List[str]):
        self.indices = indices
        self.es = elasticsearch.Elasticsearch(es_url, timeout=60)
        self.search = Search(using=self.es, index=self.indices)
        self.result = None  # Placeholder for the query results.


    def set_hits_to_zero(self):
        """Set the amount of hits returned to zero, saves network traffic."""
        self.search = self.search.extra(size=0)


    def filter_fields(self, relevant_field_paths: List[str], all_field_info: List[dict]) -> List[dict]:
        """

        :param relevant_field_paths: Name of the fields we want to keep.
        :param all_field_info: All fields we are reducing.
        :return:
        """
        without_wrong_types = list(filter(lambda x: x["type"] not in self.FILTERED_FIELD_TYPES, all_field_info))
        only_relevant_fields = list(filter(lambda x: x["path"] in relevant_field_paths, without_wrong_types))
        return only_relevant_fields


    def apply_date_filter_aggregation(self, **kwargs):
        """
        By default aggregations are applied to the whole dataset,
        to limit it you need to apply a filter aggregation with the needed
        query.
        :param kwargs:
        :return:
        """
        date_field = kwargs["date_field"]
        from_date = kwargs["from_date"]
        to_date = kwargs["to_date"]
         # You need a filter aggregation to limit the documents of other aggregations.
        date_filter = A("filter", Q("range", **{date_field: {'gte': from_date, 'lte': to_date}}))
        self.search.aggs.bucket("date_filter", date_filter)


    def apply_terms_aggregation(self, **kwargs):
        """
        Most frequent items aggregation that is being attached
        to the premade date filter aggregation.
        :param kwargs:
        :return:
        """
        target_field = kwargs["target_field"]
        aggregation_size = kwargs["aggregation_size"]
        min_doc_count = kwargs["min_doc_count"]
        # Frequent items aggregation to find posts with the same values.
        term_filter = A("terms", field="{}.keyword".format(target_field), size=aggregation_size, min_doc_count=min_doc_count)
        # Applying the previous two pre-made aggregations into the query.
        self.search.aggs["date_filter"].bucket("spam", term_filter)


    def apply_nested_terms_aggregations(self, **kwargs):
        """
        Every field send to us is being turned into a most frequent items
        aggregation that's being attached to the previous one as a nested
        aggregation to find common patterns.
        :param kwargs:
        :return:
        """
        min_doc_count = kwargs["min_doc_count"]
        aggregation_size = kwargs["aggregation_size"]
        common_feature_fields = kwargs["common_feature_fields"]

        for field in common_feature_fields:
            if field["type"] == "text":
                elastic_field_name = "{}.keyword".format(field["path"])
                self.search.aggs["date_filter"]["spam"].bucket(
                    field["path"], 
                    "terms", 
                    field=elastic_field_name,
                    size=aggregation_size
                    min_doc_count=min_doc_count)
            else:
                elastic_field_name = "{}".format(field["path"])
                self.search.aggs["date_filter"]["spam"].bucket(
                    field["path"],
                    "terms",
                    field=elastic_field_name,
                    size=aggregation_size,
                    min_doc_count=min_doc_count)


    def execute_query(self):
        self.result = self.search.execute()


    def format_elastic_response(self):
        """
        If it looks messy and unreasonable, it's because it's
        converting one data structure into a different format.
        Do not tread this unless you want to change the outcome.
        """
        ignored_keys = ["doc_count", "key"]
        container = []

        for hit in self.result.aggs.date_filter.spam.buckets:
            coocurrances = []
            frequent_texts = {"value": hit.key, "count": hit.doc_count}
            for field_name in dir(hit):
                if field_name not in ignored_keys:
                    occurrence = getattr(hit, field_name)
                    for agg in occurrence.buckets:
                        coocurrances.append({"value": agg.key, "count": agg.doc_count, "field": field_name})

            container.append({**frequent_texts, "co-occurances": coocurrances})

        self.result = container


    def get_spam_content(self, **kwargs):
        """
        Default values of the serializer should be hit into this.
        """
        self.set_hits_to_zero()
        self.apply_date_filter_aggregation(**kwargs)
        self.apply_terms_aggregation(**kwargs)
        self.apply_nested_terms_aggregations(**kwargs)
        self.execute_query()
        self.format_elastic_response()
        return self.result
