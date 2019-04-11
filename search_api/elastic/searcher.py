from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search
from query import Query
import requests
import json
from collections import defaultdict

from texta.settings import es_url


class Searcher(object):

    def __init__(self, es_url, es_use_ldap=False, es_ldap_user=None, es_ldap_password=None, default_batch=100):
        self._es_url = es_url
        self._use_ldap = False
        self._header = {"Content-Type": "application/json"}
        if es_use_ldap:
            self._requests = requests.Session()
            self._requests.auth = (es_ldap_user, es_ldap_password)
        else:
            self._requests = requests

        self._default_batch = default_batch

        self._limit = None

    def search(self, processed_request):
        index = processed_request['index']
        mapping = processed_request['mapping']

        fields = processed_request.get('_source', None)
        real_fields = processed_request.get("fields", None)

        query = json.dumps(self.create_search_query(processed_request).generate())

        if fields:
            return self._search_with_fields(index, mapping, query)
        else:
            return self._search(index, mapping, query, real_fields)

    def scroll(self, processed_request):
        index = processed_request['index']
        mapping = processed_request['mapping']

        scroll = processed_request.get('scroll', False)
        scroll_id = processed_request.get('scroll_id', None)

        fields = processed_request.get("fields", None)

        query = json.dumps(self.create_search_query(processed_request).generate())

        if scroll_id:
            return self._continue_scrolling(scroll_id)
        elif scroll:
            return self._start_scrolling(index, mapping, query, fields)

    def create_search_query(self, processed_request):
        parameters = processed_request.get('parameters', None)  # fields, size, from
        fields = processed_request.get('_source', None)

        constraints = self._differentiate_constraints(
            self._add_missing_constraint_class(processed_request['constraints'])
        )

        query = self._generate_elastic_query(constraints, parameters, fields)

        return query

    def _add_missing_constraint_class(self, constraints):
        for constraint in constraints:
            if 'class' not in constraint:
                constraint['class'] = 'string'

        return constraints

    def _generate_elastic_query(self, constraints, parameters, fields):
        query = Query()

        for constraint_class in ['string', 'date', 'fact', 'fact_val']:
            if constraint_class in constraints:
                getattr(query, 'add_%s_constraints' % constraint_class)(constraints[constraint_class])

        query.set_parameter('size', self._default_batch)

        for parameter_name in parameters:
            if parameter_name == 'limit':
                self._limit = parameters['limit']
            else:
                query.set_parameter(parameter_name, parameters[parameter_name])

        if fields:
            query.set_parameter('_source', fields)

        return query

    def _differentiate_constraints(self, constraints):
        differentiated_constraints = defaultdict(list)

        for constraint in constraints:
            differentiated_constraints[constraint['class']].append(constraint)

        return differentiated_constraints

    def _search(self, index, mapping, query, real_fields):
        query_dict = json.loads(query)

        e = Elasticsearch(es_url)
        search = Search(index=index, type=mapping).update_from_dict(query_dict).using(e)
        search = search.source(real_fields)  # Select fields to return.
        search = search[0:query_dict.get("size", 10)]  # Select how many documents to return.

        response = search.execute()
        for hit in response:
            yield hit.to_dict()

    def _search_with_fields(self, index, mapping, query):
        search_url = '{0}/{1}/{2}/_search?scroll=1m'.format(self._es_url, index, mapping)
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(self._es_url)

        response = self._requests.post(search_url, data=query, headers=self._header).json()
        scroll_id = json.dumps({'scroll_id': response['_scroll_id']})

        hits_yielded = 0
        while 'hits' in response and 'hits' in response['hits'] and response['hits']['hits']:
            for hit in response['hits']['hits']:
                if self._limit and hits_yielded == self._limit:
                    break
                for field_name in hit['_source']:
                    if field_name != 'texta_facts':
                        hit['_source'][field_name] = hit['_source'][field_name][0]
                yield hit['_source']
                hits_yielded += 1
            else:
                response = self._requests.post(scroll_url, data=scroll_id, header=self._header).json()
                continue

            response = {}

    def _start_scrolling(self, index, mapping, query, fields):
        search_url = '{0}/{1}/{2}/_search?scroll=1m'.format(self._es_url, index, mapping)
        query = json.dumps(Search().from_dict(json.loads(query)).source(fields).to_dict())  # Add field limits to the query.
        response = self._requests.post(search_url, data=query, headers=self._header).json()

        hits = response.get("hits", []).get("hits", [])
        hits = [hit["_source"] for hit in hits if hits]
        return {'hits': hits, 'scroll_id': response['_scroll_id'], 'total': response['hits']['total']}

    def _continue_scrolling(self, scroll_id):
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(self._es_url)
        response = self._requests.post(scroll_url, data=json.dumps({'scroll_id': scroll_id}), headers=self._header).json()

        hits = []
        if 'hits' in response and 'hits' in response['hits'] and response['hits']['hits']:
            for hit in response['hits']['hits']:
                    hits.append(hit['_source'])

        return {'hits': hits, 'scroll_id': scroll_id, 'total': response['hits']['total']}
