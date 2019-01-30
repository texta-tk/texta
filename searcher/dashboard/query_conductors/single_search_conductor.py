import elasticsearch_dsl

from searcher.dashboard.es_helper import DashboardEsHelper
from searcher.dashboard.metafile import BaseDashboardConductor
from typing import Dict, Any


class SingleSearchConductor(BaseDashboardConductor):
    def query_conductor(self, indices, query_body, elasticsearch, es_url, excluded_fields) -> Dict[str, Dict[str, Any]]:
        result = {}

        list_of_indices = indices.split(',')
        for index in list_of_indices:
            # Establish the connection.
            if query_body:
                search = elasticsearch_dsl.Search.from_dict(query_body).index(index).using(elasticsearch).params(typed_keys=True, size=0)
            else:
                search = elasticsearch_dsl.Search().index(index).using(elasticsearch).params(typed_keys=True, size=0)

            # Fetch all the fields and their types, then filter the ones we don't want like _texta_id.
            normal_fields, nested_fields = DashboardEsHelper(es_url=es_url, indices=index).get_aggregation_field_data()
            normal_fields, nested_fields = self._filter_fields(excluded_fields, normal_fields, nested_fields, )

            # Attach all the aggregations to Elasticsearch, depending on the fields.
            # Text, keywords get term aggs etc.
            self._normal_fields_handler(search, normal_fields)
            self._texta_facts_agg_handler(search)

            # Send the query towards Elasticsearch and then save it into the result
            # dict under its index's name.
            response = search.execute().to_dict()
            result[index] = response
            del search

        return result

    def _normal_fields_handler(self, search_dsl: elasticsearch_dsl.Search, list_of_normal_fields):
        for field_dict in list_of_normal_fields:
            field_type = field_dict['type']
            field_name = field_dict['full_path']
            bucket_name = self._format_field_to_bucket(field_name)

            # Do not play around with the #, they exist to avoid naming conflicts as awkward as they may be.
            # TODO Find a better solution for this.
            if field_type == "text":
                search_dsl.aggs.bucket(bucket_name + '#text_sigterms', 'significant_text', field=field_name, filter_duplicate_text=True)

            elif field_type == "keyword":
                search_dsl.aggs.bucket(bucket_name + '#keyword_terms', 'terms', field=field_name)
                search_dsl.aggs.bucket(bucket_name + '#keyword_count', 'value_count', field=field_name)

            elif field_type == "date":
                search_dsl.aggs.bucket(bucket_name + "_month" + "#date_month", 'date_histogram', field=field_name, interval='month')
                search_dsl.aggs.bucket(bucket_name + "_year" + "#date_year", 'date_histogram', field=field_name, interval='year')

            elif field_type == "integer":
                search_dsl.aggs.bucket(bucket_name + "#int_stats", 'extended_stats', field=field_name)
                search_dsl.aggs.bucket(bucket_name + '#int_count', 'value_count', field=field_name)

            elif field_type == "long":
                search_dsl.aggs.bucket(bucket_name + "#long_stats", 'extended_stats', field=field_name)
                search_dsl.aggs.bucket(bucket_name + '#long_count', 'value_count', field=field_name)

            elif field_type == "float":
                search_dsl.aggs.bucket(bucket_name + "#float_stats", 'extended_stats', field=field_name)
                search_dsl.aggs.bucket(bucket_name + '#float_count', 'value_count', field=field_name)

    def _texta_facts_agg_handler(self, search_dsl):
        search_dsl.aggs.bucket('texta_facts', 'nested', path='texta_facts') \
            .bucket('fact_category', 'terms', field='texta_facts.fact') \
            .bucket('significant_facts', 'significant_terms', field='texta_facts.str_val')

    def _filter_fields(self, excluded_fields, normal_fields, nested_fields):
        normal_fields = list(filter(lambda x: x['full_path'] not in excluded_fields, normal_fields))
        nested_fields = list(filter(lambda x: x['full_path'] not in excluded_fields, nested_fields))
        return normal_fields, nested_fields

    def _format_field_to_bucket(self, field_name):
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
