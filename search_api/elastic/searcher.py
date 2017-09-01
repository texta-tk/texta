from query import Query
import requests
import json
from collections import defaultdict


class Searcher(object):

    def __init__(self, es_url, es_use_ldap=False, es_ldap_user=None, es_ldap_password=None, default_batch=100):
        self._es_url = es_url
        self._use_ldap = False

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

        parameters = processed_request.get('parameters', None)  # fields, size, from
        fields = processed_request.get('fields', None)

        constraints = self._differentiate_constraints(self._add_missing_constraint_class(processed_request['constraints']))

        query = json.dumps(self._generate_elastic_query(constraints, parameters, fields))

        if fields:
            return self._search_with_fields(index, mapping, query)
        else:
            return self._search(index, mapping, query)

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
            query.set_parameter('fields', fields)

        return query.generate()

    def _differentiate_constraints(self, constraints):
        differentiated_constraints = defaultdict(list)

        for constraint in constraints:
            differentiated_constraints[constraint['class']].append(constraint)

        return differentiated_constraints

    def _search(self, index, mapping, query):
        search_url = '{0}/{1}/{2}/_search?scroll=1m'.format(self._es_url, index, mapping)
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(self._es_url)

        response = self._requests.post(search_url, data=query).json()

        scroll_id = json.dumps({'scroll_id':response['_scroll_id']})

        hits_yielded = 0
        while 'hits' in response and 'hits' in response['hits'] and response['hits']['hits']:
            for hit in response['hits']['hits']:
                if self._limit and hits_yielded == self._limit:
                    break
                yield hit['_source']
                hits_yielded += 1
            else:
                response = self._requests.post(scroll_url, data=scroll_id).json()
                continue

            response = {}

    def _search_with_fields(self, index, mapping, query):
        search_url = '{0}/{1}/{2}/_search?scroll=1m'.format(self._es_url, index, mapping)
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(self._es_url)

        response = self._requests.post(search_url, data=query).json()

        scroll_id = json.dumps({'scroll_id': response['_scroll_id']})

        hits_yielded = 0
        while 'hits' in response and 'hits' in response['hits'] and response['hits']['hits']:
            for hit in response['hits']['hits']:
                if self._limit and hits_yielded == self._limit:
                    break
                for field_name in hit['fields']:
                    if field_name != 'texta_facts':
                        hit['fields'][field_name] = hit['fields'][field_name][0]
                yield hit['fields']
                hits_yielded += 1
            else:
                response = self._requests.post(scroll_url, data=scroll_id).json()
                continue

            response = {}