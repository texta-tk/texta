import logging
from typing import Dict, List

from searcher.dashboard.metafile import BaseDashboardFormater
from texta.settings import ERROR_LOGGER


class MultiSearchFormater(BaseDashboardFormater):

    def format_result(self, response, field_counts) -> Dict[str, List[dict]]:
        """
        Main function to format the response of aggregations.
        Takes input in the form of {<index_name>: ES_agg_query_result}
        :param field_counts:
        :param response:
        :return:
        """
        response = self._format_initial_response(response)
        final_result = {'indices': []}

        for index_name, search_dict in response.items():
            reformated_agg_dict = dict()

            reformated_agg_dict["index_name"] = index_name

            total_documents = search_dict['hits']['total']
            reformated_agg_dict["total_documents"] = total_documents

            aggregations_dict = search_dict['aggregations']  # Extract the contents of ES aggregations to reformat it.
            reformated_agg_dict["aggregations"] = self._format_aggregation_dict(aggregations_dict)  # Re-add the reformatted dict into the new result.

            # Manually insert percentages into the value_counts aggregation.
            grouped_aggregations = reformated_agg_dict['aggregations']
            self._add_value_count_percentages(grouped_aggregations, total_documents, field_counts)

            final_result['indices'].append(reformated_agg_dict)

        return final_result


    def _format_initial_response(self, response):
        """
        Because MultiSearch does not contain a single response, but many it was
        needed to preformat it (to avoid more work from the existing solution) to
        add in the hits for value_count and percentage.
        :param response:
        :return:
        """
        final_result = {}
        for index, list_of_hits in response.items():
            final_result[index] = {'aggregations': {}, 'hits': {}}

            for hit in list_of_hits:
                # One of the hit values is a string for the index name.
                final_result[index]['aggregations'].update(hit['aggregations'])
                final_result[index]['hits'].update(hit['hits'])

        return final_result


    def _add_value_count_percentages(self, aggregation_dict: dict, total_document_count: int, field_counts: dict):
        """
        Traverses the previously grouped dictionary of ES aggregations, loops through the value_count
        aggregations and adds a percentage of how much a field is filled, compared to all documents.

        :param aggregation_dict: Result of ES aggregations, reformated by format_result.
        :param total_document_count: Amount of ALL the documents inside the index.
        :return:
        """
        try:
            aggregation_dict["value_count"] = {}

            for field_name, doc_count in field_counts.items():
                percentage = round(doc_count * 100 / total_document_count, 2)
                aggregation_dict["value_count"][field_name] = {'doc_count': doc_count, 'percentage': percentage}


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
