import logging
from typing import *

import elasticsearch_dsl
import elasticsearch
from searcher.dashboard.es_helper import DashboardEsHelper
from texta.settings import ERROR_LOGGER


class SearcherDashboard:

    def __init__(self, es_url: str, indices: str, query_body: dict = None, excluded_fields=('_texta_id', '_texta_id.keyword')):
        self.indices = indices
        self.es_url = es_url
        self.excluded_fields = excluded_fields
        self.query_body = query_body

        self.elasticsearch = elasticsearch.Elasticsearch(self.es_url, index=self.indices, timeout=15, )
        self.search_querys = []

        self.response = self.query_conductor()
        self.response = self.format_result()

    def query_conductor(self) -> Dict[str, Dict[str, Any]]:
        result = {}

        list_of_indices = self.indices.split(',')
        for index in list_of_indices:
            # Establish the connection.
            if self.query_body:
                search = elasticsearch_dsl.Search.from_dict(self.query_body).using(self.elasticsearch).params(typed_keys=True, size=0)
            else:
                search = elasticsearch_dsl.Search().using(self.elasticsearch).params(typed_keys=True, size=0)

            # Fetch all the fields and their types, then filter the ones we don't want like _texta_id.
            normal_fields, nested_fields = DashboardEsHelper(es_url=self.es_url, indices=index).get_aggregation_field_data()
            normal_fields, nested_fields = self._filter_fields(normal_fields, nested_fields)

            # Attach all the aggregations to Elasticsearch, depending on the fields.
            # Text, keywords get term aggs etc.
            self._normal_fields_handler(search, normal_fields)
            self._texta_facts_agg_handler(search)

            # Send the query towards Elasticsearch and then save it into the result
            # dict under its index's name.
            self.search_querys.append(search.to_dict())  # Save query for debug purposes.
            response = search.execute().to_dict()
            result[index] = response

        return result

    def format_result(self) -> Dict[str, List[dict]]:
        final_result = {'indices': []}

        for index_name, search_dict in self.response.items():
            reformated_agg_dict = dict()

            reformated_agg_dict["index_name"] = index_name

            total_documents = search_dict['hits']['total']
            reformated_agg_dict["total_documents"] = total_documents

            aggregations_dict = search_dict['aggregations']  # Extract the contents of ES aggregations to reformat it.
            reformated_agg_dict["aggregations"] = self._format_aggregation_dict(aggregations_dict)  # Re-add the reformatted dict into the new result.

            # Manually insert percentages into the value_counts aggregation.
            grouped_aggrigations = reformated_agg_dict['aggregations']
            reformated_agg_dict["aggregations"]['value_count'] = self._add_value_count_percentages(grouped_aggrigations, total_documents)

            final_result['indices'].append(reformated_agg_dict)

        return final_result

    def _normal_fields_handler(self, search_dsl: elasticsearch_dsl.Search, list_of_normal_fields):
        for field_dict in list_of_normal_fields:
            field_type = field_dict['type']
            field_name = field_dict['full_path']
            bucket_name = self._format_field_to_bucket(field_name)

            if field_type == "text":
                search_dsl.aggs.bucket(bucket_name + '#text_sigterms', 'significant_text', field=field_name)

            elif field_type == "keyword":
                search_dsl.aggs.bucket(bucket_name + '#keyword_terms', 'terms', field=field_name)
                search_dsl.aggs.bucket(bucket_name + '#keyword_count', 'value_count', field=field_name)

            elif field_type == "date":
                search_dsl.aggs.bucket(bucket_name + "_month#date_month", 'date_histogram', field=field_name, interval='month')
                search_dsl.aggs.bucket(bucket_name + "_year#date_year", 'date_histogram', field=field_name, interval='year')

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

    def _add_value_count_percentages(self, aggregation_dict: dict, total_document_count: int):
        """
        Traverses the previously grouped dictionary of ES aggregations, loops through the value_count
        aggregations and adds a percentage of how much a field is filled, compared to all documents.

        :param aggregation_dict: Result of ES aggregations, reformated by format_result.
        :param total_document_count: Amount of ALL the documents inside the index.
        :return:
        """
        try:
            value_count_fields = aggregation_dict['value_count']
            for field_name, agg_dict in value_count_fields.items():
                field_count = agg_dict['value']
                agg_dict['percentage'] = round(field_count * 100 / total_document_count, 2)

            return value_count_fields

        except ZeroDivisionError as e:
            logging.getLogger(ERROR_LOGGER).exception(e)

    def _format_aggregation_dict(self, agg_dict: dict):
        """
        Taking the aggregation results of a single index, format it into the
        desired input.

        Different types of aggregations are grouped together by their type.

        :param agg_dict: Result of Elasticsearch's aggregations.
        :return: Aggregations dictionary in the desired format.
        """
        final_result = dict()

        # Categorize all the aggregations into groups, depending on their agg-type (ex sterms, value_counts, extended_stats etc)
        for field_name, aggregation_dict in agg_dict.items():

            if 'texta_facts' not in field_name:
                agg_type, field_name, bucket_suffix = field_name.split('#')
            else:
                agg_type, field_name, bucket_suffix = ('nested', 'texta_facts', '')

            if agg_type not in final_result:
                # Field names are in format agg_type#bucket_name which contains the field_name.
                # Keep only the bucket/field name for better parsing in the front end.
                final_result[agg_type] = {field_name: aggregation_dict}
            else:
                final_result[agg_type].update({field_name: aggregation_dict})

        return final_result

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

    def _filter_fields(self, normal_fields, nested_fields):
        normal_fields = list(filter(lambda x: x['full_path'] not in self.excluded_fields, normal_fields))
        nested_fields = list(filter(lambda x: x['full_path'] not in self.excluded_fields, nested_fields))
        return normal_fields, nested_fields
