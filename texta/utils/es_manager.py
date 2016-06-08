# -*- coding: utf8 -*-
import json
import re

import requests

from ..conceptualiser.models import Concept
from ..conceptualiser.models import TermConcept
from ..utils.log_manager import LogManager

from settings import es_url


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ES_Cache:
    """ ES Cache for facts index
    """
    __metaclass__ = Singleton

    MAX_LIMIT = 10000

    def __init__(self):
        self._cache = {}
        self._last_used = []

    def cache_hit(self, q):
        return q in self._cache

    def get_data(self, q):
        self._update_usage(q)
        return self._cache[q]

    def _update_usage(self, q):
        if q in self._last_used:
            self._last_used.remove(q)
        self._last_used.insert(0, q)

    def _check_limit(self):
        # If is over limit, clean 1/3 of last used data
        if len(self._last_used) > self.MAX_LIMIT:
            keep_index = int(self.MAX_LIMIT * 0.66)
            for i in self._last_used[keep_index:]:
                del self._cache[i]
            self._last_used = self._last_used[0:keep_index]

    def set_data(self, q, data):
        self._cache[q] = data
        self._update_usage(q)
        self._check_limit()

    def clean_cache(self):
        self._cache = {}
        self._last_used = []


class ES_Manager:
    """ Manage Elasticsearch operations and interface
    """

    TEXTA_MAPPING = 'texta'
    TEXTA_RESERVED = ['texta_link']

    def __init__(self, index, mapping, date_range, url=None):
        self.es_url = url if url else es_url
        self.index = index
        self.mapping = mapping
        self.date_range = date_range
        self.combined_query = None
        self._facts_map = None
        self.es_cache = ES_Cache()

    def check_if_field_has_facts(self, sub_fields):
        """ Check if field is associate with facts in Elasticsearch
        """
        doc_type = self.mapping.lower()
        field_path = [s.lower() for s in sub_fields]
        doc_path = '.'.join(field_path)

        request_url = '{0}/{1}/{2}/_count'.format(es_url, self.index, self.TEXTA_MAPPING)
        q = {"query": {"bool": {"filter": {'and': []}}}}
        q['query']['bool']['filter']['and'].append({"term": {'facts.doc_type': doc_type}})
        q['query']['bool']['filter']['and'].append({"term": {'facts.doc_path': doc_path}})
        q = json.dumps(q)
        response = requests.post(request_url, data=q).json()
        return response['count'] > 0

    def _decode_mapping_structure(self, structure, root_path=list()):
        """ Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []

        for item in structure.items():
            if 'properties' in item[1]:
                sub_structure = item[1]['properties']
                path_list = root_path[:]
                path_list.append(item[0])
                sub_mapping = self._decode_mapping_structure(sub_structure, root_path=path_list)
                mapping_data.extend(sub_mapping)
            else:
                path_list = root_path[:]
                path_list.append(item[0])
                if path_list[0] not in self.TEXTA_RESERVED:
                    path = '.'.join(path_list)
                    data = {'path': path, 'type': item[1]['type']}
                    mapping_data.append(data)

        return mapping_data

    def get_mapped_fields(self):
        """ Get flat structure of fields from Elasticsearch mapping
        """
        mapping_structure = requests.get(es_url+'/'+self.index).json()[self.index]['mappings'][self.mapping]['properties']
        mapping_data = self._decode_mapping_structure(mapping_structure)
        return mapping_data

    def get_column_names(self):
        """ Get Column names from flat mapping structure
            Returns: sorted list of names
        """
        mapped_fields = self.get_mapped_fields()
        column_names = [c['path'] for c in mapped_fields if not self._is_reserved_field(c['path'])]
        column_names.sort()
        return column_names

    def _is_reserved_field(self, field_name):
        """ Check if a field is a TEXTA reserved name
        """
        reserved = False
        for r in self.TEXTA_RESERVED:
            if r in field_name:
                reserved = True
        return reserved

    @staticmethod
    def _get_match_constraints(es_params):
        _constraints = {}
        for item in es_params:
            if 'match' in item:
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]
        return _constraints

    @staticmethod
    def _get_daterange_constraints(es_params):
        _constraints = {}
        for item in es_params:
            if 'daterange' in item:
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]
        return _constraints

    @staticmethod
    def _get_fact_constraints(es_params):
        _constraints = {}
        for item in es_params:
            if 'fact' in item:
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]
        return _constraints

    @staticmethod
    def _get_list_synonyms(query_string):
        """ check if string is a concept identifier
        """
        synonyms = []
        concept = re.search('^@(\d)+-', query_string)
        if concept:
            concept_id = int(concept.group()[1:-1])
            for term in TermConcept.objects.filter(concept=Concept.objects.get(pk=concept_id)):
                synonyms.append(term.term.term)
        else:
            synonyms.append(query_string)
        return synonyms

    def build(self, es_params):
        """ Build internal representation for queries using es_params

            A combined query is a dictionary D containing:

                D['main']   ->  the main elasticsearch query
                D['facts']  ->  the fact query

        """
        _combined_query = {"main": {"query": {"bool": {"should": [], "must": [], "must_not": []}}},
                           "facts": {"include": [], 'total_include': 0,
                                     "exclude": [], 'total_exclude': 0}}

        string_constraints = self._get_match_constraints(es_params)
        date_constraints = self._get_daterange_constraints(es_params)
        fact_constraints = self._get_fact_constraints(es_params)

        for string_constraint in string_constraints.values():

            match_field = string_constraint['match_field'] if 'match_field' in string_constraint else ''
            match_type = string_constraint['match_type'] if 'match_type' in string_constraint else ''
            match_slop = string_constraint["match_slop"] if 'match_slop' in string_constraint else ''
            match_operator = string_constraint['match_operator'] if 'match_operator' in string_constraint else ''

            query_strings = [s.replace('\r','') for s in string_constraint['match_txt'].split('\n')]
            query_strings = [s for s in query_strings if s]
            sub_queries = []

            for query_string in query_strings:
                synonyms = self._get_list_synonyms(query_string)
                # construct synonym queries
                synonym_queries = []
                for synonym in synonyms:
                    synonym_query = {}
                    if match_type == 'match':
                        # match query
                        sub_query = {'query': synonym, 'operator': 'and'}
                        synonym_query['match'] = {match_field: sub_query}
                    if match_type == 'match_phrase':
                        # match phrase query
                        sub_query = {'query': synonym, 'slop': match_slop}
                        synonym_query['match_phrase'] = {match_field: sub_query}
                    if match_type == 'match_phrase_prefix':
                        # match phrase prefix query
                        sub_query = {'query': synonym, 'slop': match_slop}
                        synonym_query['match_phrase_prefix'] = {match_field: sub_query}
                    synonym_queries.append(synonym_query)
                sub_queries.append({'bool': {'minimum_should_match': 1,'should': synonym_queries}})
            _combined_query["main"]["query"]["bool"]["should"].append({"bool": {match_operator: sub_queries}})
        _combined_query["main"]["query"]["bool"]["minimum_should_match"] = len(string_constraints)

        for date_constraint in date_constraints.values():
            date_range_start = {"range": {date_constraint['daterange_field']: {"gte": date_constraint['daterange_from']}}}
            date_range_end= {"range": {date_constraint['daterange_field']: {"lte": date_constraint['daterange_to']}}}
            _combined_query["main"]['query']['bool']['must'].append(date_range_start)
            _combined_query["main"]['query']['bool']['must'].append(date_range_end)

        total_include = 0
        for fact_constraint in fact_constraints.values():
            fact_field = fact_constraint['fact_field'] if 'fact_field' in fact_constraint else ''
            fact_txt = fact_constraint['fact_txt'] if 'fact_txt' in fact_constraint else ''
            fact_operator = fact_constraint['fact_operator'] if 'fact_operator' in fact_constraint else ''
            query_strings = [s.replace('\r', '') for s in fact_txt.split('\n')]
            query_strings = [s.lower() for s in query_strings if s]
            sub_queries = []
            # Add facts query to search in facts mapping
            fact_queries = []
            for query_string in query_strings:
                fact_q = {"bool": {"must": []}}
                fact_q['bool']['must'].append({'match_phrase': {'facts.fact': {'query': query_string, 'slop': 1}}})
                fact_q['bool']['must'].append({'term': {'facts.doc_type': self.mapping.lower()}})
                fact_q['bool']['must'].append({'term': {'facts.doc_path': fact_field.lower()}})
                fact_queries.append(fact_q)
            if fact_operator in ['must', 'should']:
                _combined_query['facts']['include'].append({'query': {"bool": {fact_operator: fact_queries}}})
                total_include += 1

            # Fact queries are executed against the fact in texta_link
            for query_string in query_strings:
                fact_link = '{0}.{1}'.format(fact_field, query_string)
                sub_query = { "match_phrase" : { "texta_link.facts" : fact_link } }
                sub_queries.append(sub_query)
            _combined_query["main"]["query"]["bool"]["should"].append({"bool": {fact_operator: sub_queries}})

        _combined_query["main"]["query"]["bool"]["minimum_should_match"] += len(fact_constraints)
        _combined_query['facts']['total_include'] = total_include
        _combined_query['facts']['total_exclude'] = 0
        self.combined_query = _combined_query

    def get_combined_query(self):
        return self.combined_query

    def load_combined_query(self, combined_query):
        self.combined_query = combined_query

    def set_query_parameter(self, key, value):
        """ Set query[key] = value in the main query structure
        """
        self.combined_query['main'][key] = value

    def _check_if_qmain_is_empty(self):
        _must = len(self.combined_query['main']["query"]["bool"]["must"])
        _should = len(self.combined_query['main']["query"]["bool"]["should"])
        _must_not = len(self.combined_query['main']["query"]["bool"]["must_not"])
        return _must == 0 and _should == 0 and _must_not == 0

    def _check_if_qfacts_is_empty(self):
        _include = self.combined_query['facts']['total_include']
        _exclude = self.combined_query['facts']['total_exclude']
        return _include == 0 and _exclude == 0

    def is_combined_query_empty(self):
        _empty_facts = self._check_if_qmain_is_empty()
        _empty_main = self._check_if_qfacts_is_empty()
        return _empty_facts and _empty_main

    def _get_facts_ids_map(self, q, max_size):
        fm = {}
        q = json.dumps(q)

        if self.es_cache.cache_hit(q):
            return self.es_cache.get_data(q)

        scroll_url = '{0}/_search/scroll?scroll=1m'.format(es_url)
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=1000'.format(es_url, self.index, self.TEXTA_MAPPING)
        response = requests.post(search_url, data=q).json()
        scroll_id = response['_scroll_id']
        total_msg = response['hits']['total']
        count_limit = 0
        while (total_msg > 0) and (count_limit < max_size):
            response = requests.post(scroll_url, data=scroll_id).json()
            scroll_id = response['_scroll_id']
            total_msg = len(response['hits']['hits'])
            count_limit += total_msg
            for hit in response['hits']['hits']:
                doc_id = str(hit['_source']['facts']['doc_id'])
                doc_path = hit['_source']['facts']['doc_path']
                spans = hit['_source']['facts']['spans']
                spans = json.loads(spans)
                if doc_id not in fm:
                    fm[doc_id] = {}
                if doc_path not in fm[doc_id]:
                    fm[doc_id][doc_path] = []
                fm[doc_id][doc_path].extend(spans)

        self.es_cache.set_data(q, fm)
        return fm

    @staticmethod
    def _merge_maps(temp_map_list, union=False):
        final_map = {}
        key_set_list = [set(m.keys()) for m in temp_map_list]
        if union:
            intersection_set = reduce(lambda a, b: a | b, key_set_list)
        else:
            intersection_set = reduce(lambda a, b: a & b, key_set_list)
        # Merge all maps:
        for k in intersection_set:
            for m in temp_map_list:
                if k not in final_map:
                    final_map[k] = {}
                for sub_k in m[k]:
                    if sub_k not in final_map[k]:
                        final_map[k][sub_k] = []
                    final_map[k][sub_k].extend(m[k][sub_k])
        return final_map

    # def _process_facts(self, max_size=1000000):
    #     self._facts_map = {'include': {}, 'exclude': {}, 'has_include': False, 'has_exclude': False}
    #     if not self._check_if_qfacts_is_empty():
    #         q_facts = self.combined_query['facts']
    #
    #         if q_facts['total_include'] > 0:
    #             # Include queries should be merged with intersection of their doc_ids
    #             temp_map_list = []
    #             for sub_q in q_facts['include']:
    #                 q = {"query": sub_q['query']}
    #                 temp_map = self._get_facts_ids_map(q, max_size)
    #                 temp_map_list.append(temp_map)
    #             self._facts_map['include'] = self._merge_maps(temp_map_list)
    #             self._facts_map['has_include'] = True
    #
    #         if q_facts['total_exclude'] > 0:
    #             # Exclude queries should be merged with union of their doc_ids
    #             temp_map_list = []
    #             for sub_q in q_facts['exclude']:
    #                 q = {"query": sub_q['query']}
    #                 temp_map = self._get_facts_ids_map(q, max_size)
    #                 temp_map_list.append(temp_map)
    #             self._facts_map['exclude'] = self._merge_maps(temp_map_list, union=True)
    #             self._facts_map['has_exclude'] = True

    def _get_restricted_facts(self, doc_ids, max_size=500):
        facts_map = {'include': {}, 'exclude': {}, 'has_include': False, 'has_exclude': False}
        if not self._check_if_qfacts_is_empty():
            q_facts = self.combined_query['facts']
            if q_facts['total_include'] > 0:
                # Include queries should be merged with intersection of their doc_ids
                temp_map_list = []
                for sub_q in q_facts['include']:
                    q = {"query": sub_q['query']}
                    q['query']['bool']['filter'] = {'and': []}
                    q['query']['bool']['filter']['and'].append({"terms": {'facts.doc_id': doc_ids}})
                    temp_map = self._get_facts_ids_map(q, max_size)
                    temp_map_list.append(temp_map)
                facts_map['include'] = self._merge_maps(temp_map_list)
                facts_map['has_include'] = True
        return facts_map

    def get_facts_map(self, doc_ids=[]):
        """ Returns facts map with doc ids and spans values
        """
        return self._get_restricted_facts(doc_ids)
        # if not self._facts_map:
        #    self._process_facts()
        # return self._facts_map

    # def _get_joint_query(self, apply_facts_join = True):
    #    q = self.combined_query['main']
    #    if apply_facts_join:
    #        # Application Joint
    #        facts_map = self.get_facts_map()
    #        if facts_map['has_include']:
    #            doc_ids = facts_map['include'].keys()
    #            ids_join = {"ids": {"values": doc_ids}}
    #            q['query']['bool']['must'].append(ids_join)
    #        if facts_map['has_exclude']:
    #            doc_ids = facts_map['exclude'].keys()
    #            ids_join = {"ids": {"values": doc_ids}}
    #            q['query']['bool']['must_not'].append(ids_join)
    #    return q

    def search(self):
        """ Search
        """
        q = json.dumps(self.combined_query['main'])
        search_url = '{0}/{1}/{2}/_search'.format(es_url, self.index, self.mapping)
        response = requests.post(search_url, data=q).json()
        return response

    def scroll(self, scroll_id=None, time_out='1m'):
        """ Search and Scroll
        """
        if scroll_id:
            q = json.dumps({"scroll": time_out, "scroll_id": scroll_id})
            search_url = '{0}/_search/scroll'.format(es_url)
        else:
            q = json.dumps(self.combined_query['main'])
            search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll={3}'.format(es_url, self.index,
                                                                                  self.mapping, time_out)

        response = requests.post(search_url, data=q).json()
        return response

    def get_total_documents(self):
        search_url = '{0}/{1}/{2}/_count'.format(es_url, self.index, self.mapping)
        q = json.dumps(self.combined_query['main'])
        response = requests.post(search_url, data=q).json()
        total = response['count']
        return long(total)

    def get_facts_structure(self):
        """ Get facts structure
            Returns: dictionary in the form {fact: [set of fields]}
        """
        # TODO: change to aggregation over unique elements
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=1000'.format(es_url, self.index, self.TEXTA_MAPPING)
        query = {"query": {"term": {"facts.doc_type": self.mapping.lower()}}}
        query = json.dumps(query)
        response = requests.post(search_url, data=query).json()
        scroll_id = response['_scroll_id']
        total = response['hits']['total']
        facts_structure = {}
        while total > 0:
            response = requests.post('{0}/_search/scroll?scroll=1m'.format(es_url), data=scroll_id).json()
            total = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            for hit in response['hits']['hits']:
                fact = hit['_source']['facts']['fact']
                doc_path = hit['_source']['facts']['doc_path']
                if fact not in facts_structure:
                    facts_structure[fact] = set()
                facts_structure[fact].add(doc_path)
        return facts_structure

    def get_facts_from_field(self, field):
        """ Get all facts from a specific field
            Returns: Dictionary in the from {fact: [set of doc_id]}
        """
        logger = LogManager(__name__, 'ES MANAGER')

        doc_type = self.mapping.lower()
        doc_path = field.lower()

        query = {"query": {"bool": {"filter": {'and': []}}}, 'fields': ['facts.fact', 'facts.doc_id']}
        query['query']['bool']['filter']['and'].append({"term": {'facts.doc_type': doc_type}})
        query['query']['bool']['filter']['and'].append({"term": {'facts.doc_path': doc_path}})
        query = json.dumps(query)

        search_param = 'search_type=scan&scroll=1m&size=1000'
        search_url = '{0}/{1}/{2}/_search?{3}'.format(es_url, self.index, self.TEXTA_MAPPING, search_param)
        response = requests.post(search_url, data=query).json()
        scroll_id = response['_scroll_id']
        total = response['hits']['total']
        facts = {}
        while total > 0:
            response = requests.post('{0}/_search/scroll?scroll=1m'.format(es_url), data=scroll_id).json()
            total = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            for hit in response['hits']['hits']:
                try:
                    fact = hit['fields']['facts.fact'][0]
                    doc_id = hit['fields']['facts.doc_id'][0]
                    if fact not in facts:
                        facts[fact] = set()
                    facts[fact].add(doc_id)
                except Exception, e:
                    print '-- Exception[{0}] {1}'.format(__name__, e)
                    logger.set_context('hit', hit)
                    logger.exception('facts_error', msg='Problem with facts structure')
        return facts
