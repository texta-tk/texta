from dateutil.relativedelta import relativedelta
from datetime import datetime
from query import Query
from searcher import Searcher
import requests
import json


class Aggregator(object):

    def __init__(self, date_format, es_url):
        self._date_format = date_format
        self._searcher = Searcher(es_url)
        self._es_url = es_url

    def aggregate(self, processed_request):
        aggregation_subquery = self._prepare_aggregation_subquery(processed_request['aggregation'])

        aggregation_results = []
        for search in processed_request['searches']:
            query = self._searcher.create_search_query(search)
            query.set_parameter('aggs', aggregation_subquery)
            query.set_parameter('size', 0)
            aggregation_results.append(self._get_aggregation_results(search['index'], search['mapping'], query.generate()))

        return aggregation_results

    def _get_aggregation_results(self, index, mapping, query):
        response = requests.post('{0}/{1}/{2}/_search'.format(self._es_url, index, mapping), data=json.dumps(query))
        return response.json()['aggregations']

    def _prepare_aggregation_subquery(self, aggregation_steps):
        final_aggregation_subquery = {}
        aggregation_subquery = final_aggregation_subquery

        previous_step_type = None
        for aggregation_step in aggregation_steps:
            aggregation_subquery = self._add_aggregation_level(aggregation_subquery, aggregation_step, previous_step_type)
            previous_step_type = aggregation_step['type']

        return final_aggregation_subquery

    def _add_aggregation_level(self, query, aggregation_step, previous_step_type=None):

        type_ = aggregation_step['type']
        field = aggregation_step['field']

        if type_ == 'string':
            subquery, milestone = self._get_string_subquery(type_, field, aggregation_step['sort_by'])
        elif type_ == 'daterange':
            date_range = {'min': aggregation_step['start'], 'max': aggregation_step['end']}
            ranges = self._get_date_intervals(date_range, aggregation_step['interval'])[0]
            subquery, milestone = self._get_daterange_subquery(type_, field, ranges)
        elif type_ == 'fact':
            subquery, milestone = self._get_fact_subquery(type_, 'fact')
        elif type_ == 'fact_str':
            subquery, milestone = self._get_fact_subquery(type_, 'str_val')
        elif type  == 'fact_num':
            subquery, milestone = self._get_fact_subquery(type_, 'num_val')

        if previous_step_type == 'fact' and type_ == 'fact_str':
            query['aggs'] = subquery[type_]['aggs']
            query['aggs']['documents'] = {"reverse_nested": {}}
        elif previous_step_type and previous_step_type.startswith('fact') and type_ == 'string':
            query['aggs']['documents']['aggs'] = subquery
        else:
            if previous_step_type:
                query["aggregations"] = subquery
            else:
                for key in subquery:
                    query[key] = subquery[key]

        return milestone

    def _get_daterange_subquery(self, aggregation_name, field_path, ranges):
        subquery = {
            aggregation_name: {"date_range": {"field": field_path, "format": self._date_format, "ranges": ranges}}
        }

        milestone = subquery[aggregation_name]

        return subquery, milestone

    def _get_string_subquery(self, aggregation_name, field_path, sort_by):
        # NOTE: Exclude numbers from discrete aggregation ouput
        subquery = {aggregation_name: {sort_by: {"field": field_path, "size": 30}}}
        milestone = subquery[aggregation_name]

        return subquery, milestone

    def _get_fact_subquery(self, aggregation_name, fact_field):
        subquery = {
            aggregation_name: {
                "nested": {"path": "texta_facts"},
                "aggs": {
                    aggregation_name: {
                        "significant_terms": {"field": "texta_facts.{0}".format(fact_field) , "size": 30},
                        "aggs": {"documents": {"reverse_nested": {}}}
                    }
                }
            }
        }

        milestone = subquery[aggregation_name]['aggs'][aggregation_name]

        return subquery, milestone

    @staticmethod
    def _get_date_intervals(daterange, interval):
        if daterange['min'] and daterange['max']:
            frmt = "%Y-%m-%d"
            start_datetime = datetime.strptime(daterange['min'], frmt)
            end_datetime = datetime.strptime(daterange['max'], frmt)

            if interval == 'year':
                rdelta = relativedelta(years=+1)
            elif interval == 'quarter':
                rdelta = relativedelta(months=+3)
            elif interval == 'month':
                rdelta = relativedelta(months=+1)
            elif interval == 'week':
                rdelta = relativedelta(weeks=+1)
            elif interval == 'day':
                rdelta = relativedelta(days=+1)

            next_calculated_datetime = start_datetime + rdelta
            dates = [start_datetime, next_calculated_datetime]
            labels = [start_datetime.strftime(frmt), next_calculated_datetime.strftime(frmt)]

            while next_calculated_datetime < end_datetime:
                next_calculated_datetime += rdelta
                dates.append(next_calculated_datetime)
                labels.append(next_calculated_datetime.strftime(frmt))

            dates.append(end_datetime)
            labels.append(end_datetime.strftime(frmt))

            dates_str = []
            for i, date in enumerate(dates[1:]):
                dates_str.append({'from': dates[i].strftime(frmt), 'to': date.strftime(frmt)})

            return dates_str, labels

        else:

            return [], []