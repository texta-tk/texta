from typing import Dict, Any

import elasticsearch_dsl
from elasticsearch_dsl import MultiSearch

from searcher.dashboard.es_helper import DashboardEsHelper


class MultiSearchConductor:
    def __init__(self):
        self.multi_search = MultiSearch()

    def query_conductor(self, indices, query_body, elasticsearch, es_url, excluded_fields):
        result = {}

        list_of_indices = indices.split(',')

        for index in list_of_indices:
            # Fetch all the fields and their types, then filter the ones we don't want like _texta_id.
            normal_fields, nested_fields = DashboardEsHelper(es_url=es_url, indices=index).get_aggregation_field_data()
            normal_fields, nested_fields = self._filter_excluded_fields(excluded_fields, normal_fields, nested_fields, )

            # Attach all the aggregations to Elasticsearch, depending on the fields.
            # Text, keywords get term aggs etc.
            self._normal_fields_handler(normal_fields, index=index, query_body=query_body, elasticsearch=elasticsearch)
            self._texta_facts_agg_handler(index=index, query_body=query_body, elasticsearch=elasticsearch)

            # Send the query towards Elasticsearch and then save it into the result
            # dict under its index's name.
            responses = self.multi_search.using(elasticsearch).execute()
            result[index] = [response.to_dict() for response in responses]

        return result

    def _normal_fields_handler(self, list_of_normal_fields, query_body, index, elasticsearch):
        for field_dict in list_of_normal_fields:
            field_type = field_dict['type']
            field_name = field_dict['full_path']
            bucket_name = self._remove_dot_notation(field_name)

            # Do not play around with the #, they exist to avoid naming conflicts as awkward as they may be.
            # TODO Find a better solution for this.
            if field_type == "text":
                if query_body is not None:
                    search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
                    search_dsl.aggs.bucket("sigsterms#" + bucket_name + '#text_sigterms', 'significant_text', field=field_name, filter_duplicate_text=True)
                    self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "keyword":
                search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
                search_dsl.aggs.bucket("sterms#" + bucket_name + '#keyword_terms', 'terms', field=field_name)
                search_dsl.aggs.bucket("value_count#" + bucket_name + '#keyword_count', 'value_count', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "date":
                search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
                search_dsl.aggs.bucket("date_histogram#" + bucket_name + "_month" + "#date_month", 'date_histogram', field=field_name, interval='month')
                search_dsl.aggs.bucket("date_histogram#" + bucket_name + "_year" + "#date_year", 'date_histogram', field=field_name, interval='year')
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "integer":
                search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
                search_dsl.aggs.bucket("extended_stats#" + bucket_name + "#int_stats", 'extended_stats', field=field_name)
                search_dsl.aggs.bucket("value_count#" + bucket_name + '#int_count', 'value_count', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "long":
                search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
                search_dsl.aggs.bucket("extended_stats#" + bucket_name + "#long_stats", 'extended_stats', field=field_name)
                search_dsl.aggs.bucket("value_count#" + bucket_name + '#long_count', 'value_count', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "float":
                search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
                search_dsl.aggs.bucket("extended_stats#" + bucket_name + "#float_stats", 'extended_stats', field=field_name)
                search_dsl.aggs.bucket("value_count#" + bucket_name + '#float_count', 'value_count', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

    def _texta_facts_agg_handler(self, query_body, index, elasticsearch):
        search_dsl = self._create_search_object(query_body=query_body, index=index, elasticsearch=elasticsearch)
        search_dsl.aggs.bucket("nested#" + 'texta_facts', 'nested', path='texta_facts') \
            .bucket('sterms#fact_category', 'terms', field='texta_facts.fact', collect_mode="breadth_first") \
            .bucket("sigsterms#" + 'significant_facts', 'significant_terms', field='texta_facts.str_val')
        self.multi_search = self.multi_search.add(search_dsl)

    def _filter_excluded_fields(self, excluded_fields, normal_fields, nested_fields):
        normal_fields = list(filter(lambda x: x['full_path'] not in excluded_fields, normal_fields))
        nested_fields = list(filter(lambda x: x['full_path'] not in excluded_fields, nested_fields))
        return normal_fields, nested_fields

    def _remove_dot_notation(self, field_name):
        """
        Removes all the .'s in the field names to avoid
        potential conflicts in the front end.

        :param field_name: Name of a field inside Elasticsearch, ex article_lead.keyword
        :return: Name of the field but the comma removed. ex article_lead
        """
        if '.' in field_name:
            field_name = field_name.split('.')[0]
            return field_name
        else:
            return field_name

    def _create_search_object(self, query_body, index, elasticsearch):
        if query_body:
            search = elasticsearch_dsl.Search.from_dict(query_body).index(index).using(elasticsearch).extra(size=0).source(False)
            return search
        else:
            search = elasticsearch_dsl.Search().index(index).extra(size=0).source(False)
            return search
