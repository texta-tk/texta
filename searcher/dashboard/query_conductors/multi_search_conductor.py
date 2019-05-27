import logging

import elasticsearch_dsl
import elasticsearch
from elasticsearch_dsl import MultiSearch

from searcher.dashboard.es_helper import DashboardEsHelper
from texta.settings import ERROR_LOGGER


class MultiSearchConductor:
    def __init__(self):
        self.field_counts = {}
        self.multi_search = MultiSearch()

    def query_conductor(self, indices, query_body, es, es_url, excluded_fields):
        result = {}

        list_of_indices = indices.split(',')

        for index in list_of_indices:
            # Fetch all the fields and their types, then filter the ones we don't want like _texta_id.
            normal_fields, nested_fields = DashboardEsHelper(es_url=es_url, indices=index).get_aggregation_field_data()
            normal_fields, nested_fields = self._filter_excluded_fields(excluded_fields, normal_fields, nested_fields, )

            # Attach all the aggregations to Elasticsearch, depending on the fields.
            # Text, keywords get term aggs etc.
            self._normal_fields_handler(normal_fields, index=index, query_body=query_body, es=es)
            self._texta_facts_agg_handler(index=index, query_body=query_body, es=es)

            # Send the query towards Elasticsearch and then save it into the result
            # dict under its index's name.
            try:
                responses = self.multi_search.using(es).execute()
                result[index] = [response.to_dict() for response in responses]

            except elasticsearch.exceptions.TransportError as e:
                logging.getLogger(ERROR_LOGGER).exception(e.info)
                raise elasticsearch.exceptions.TransportError

        return result

    def _normal_fields_handler(self, list_of_normal_fields, query_body, index, es):
        for field_dict in list_of_normal_fields:
            field_type = field_dict['type']
            field_name = field_dict['full_path']
            clean_field_name = self._remove_dot_notation(field_name)

            search_gateway = elasticsearch_dsl.Search(index=index).using(es)
            self.field_counts[field_name] = search_gateway.query("exists", field=clean_field_name).count()

            # Do not play around with the #, they exist to avoid naming conflicts as awkward as they may be.
            # TODO Find a better solution for this.
            if field_type == "text":
                if query_body is not None:
                    search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)
                    search_dsl.aggs.bucket("sigsterms#{0}#text_sigterms".format(field_name), 'significant_text', field=field_name, filter_duplicate_text=True)
                    self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "keyword":
                search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)
                search_dsl.aggs.bucket("sterms#{0}#keyword_terms".format(field_name), 'terms', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "date":
                search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)
                search_dsl.aggs.bucket("date_histogram#{0}_month#date_month".format(field_name), 'date_histogram', field=field_name, interval='month')
                search_dsl.aggs.bucket("date_histogram#{0}_year#date_year".format(field_name), 'date_histogram', field=field_name, interval='year')
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "integer":
                search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)
                search_dsl.aggs.bucket("extended_stats#{0}#int_stats".format(field_name), 'extended_stats', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "long":
                search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)
                search_dsl.aggs.bucket('extended_stats#{0}#long_stats'.format(field_name), 'extended_stats', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

            elif field_type == "float":
                search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)
                search_dsl.aggs.bucket("extended_stats#{0}#float_stats".format(field_name), 'extended_stats', field=field_name)
                self.multi_search = self.multi_search.add(search_dsl)

    def _texta_facts_agg_handler(self, query_body, index, es):
        search_dsl = self._create_search_object(query_body=query_body, index=index, es=es)

        search_dsl.aggs.bucket("nested#texta_facts", 'nested', path='texta_facts') \
            .bucket('sterms#fact_category', 'terms', field='texta_facts.fact', collect_mode="breadth_first") \
            .bucket("sigsterms#significant_facts", 'significant_terms', field='texta_facts.str_val')

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

    def _create_search_object(self, query_body, index, es):
        if query_body:
            search = elasticsearch_dsl.Search.from_dict(query_body).index(index).using(es).extra(size=0).source(False)
            return search
        else:
            search = elasticsearch_dsl.Search().index(index).extra(size=0).source(False)
            return search
