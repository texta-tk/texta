# -*- coding: utf8 -*-
import json
import re

import requests

from conceptualiser.models import Concept
from conceptualiser.models import TermConcept
from settings import es_url


class ES_Manager:
    """ Manage Elasticsearch operations and interface
    """

    TEXTA_MAPPING = 'texta'

    def __init__(self, index, mapping, date_range, url=None):
        self.es_url = url if url else es_url
        self.index = index
        self.mapping = mapping
        self.date_range = date_range
        self.combined_query = None
        self._facts_map = None

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
        column_names = [c['path'] for c in mapped_fields]
        column_names.sort()
        return column_names

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
                D['facts']  ->  the restrictive fact query

        """
        _combined_query = {"main": {"query": {"bool": {"should": [], "must": []}}},
                           "facts": {"query": {"bool": {"should": [], "must": []}}}}

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
                ### construct synonym queries
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

        for fact_constraint in fact_constraints.values():
            fact_field = fact_constraint['fact_field'] if 'fact_field' in fact_constraint else ''
            fact_txt = fact_constraint['fact_txt'] if 'fact_txt' in fact_constraint else ''
            query_strings = [s.replace('\r', '') for s in fact_txt.split('\n')]
            query_strings = [s for s in query_strings if s]
            #sub_queries = []
            for query_string in query_strings:
                q = {"query": {"bool": {"filter": {'and': []}}}}
                q['query']['bool']['filter']['and'].append({"term": {'facts.doc_type': self.mapping.lower()}})
                q['query']['bool']['filter']['and'].append({"term": {'facts.doc_path': fact_field}})
                q['query']['bool']['filter']['and'].append({"prefix": {'facts.fact': query_string}})
                _combined_query["facts"]["query"]["bool"]["should"].append(q)

        self.combined_query = _combined_query

    def get_combined_query(self):
        return self.combined_query

    def load_combined_query(self, combined_query):
        self.combined_query = combined_query

    def set_query_parameter(self, key, value):
        """ Set query[key] = value in the main query structure
        """
        self.combined_query['main'][key] = value

    def _check_if_empty(self, key):
        _must = len(self.combined_query[key]["query"]["bool"]["must"])
        _should = len(self.combined_query[key]["query"]["bool"]["should"])
        return _must == 0 and _should == 0

    def is_combined_query_empty(self):
        _empty_facts = self._check_if_empty('facts')
        _empty_main = self._check_if_empty('main')
        return _empty_facts and _empty_main

    def _process_facts(self, max_size=10000):
        self._facts_map = {}
        if not self._check_if_empty('facts'):
            q_facts = self.combined_query['facts']
            q_facts = json.dumps(q_facts)
            search_url = '{0}/{1}/{2}/_search?size={2}'.format(es_url, self.index, max_size, self.TEXTA_MAPPING)
            response = requests.post(search_url, data=q_facts).json()
            for hit in response['hits']['hits']:
                doc_id = hit['_source']['facts']['doc_id']
                doc_path = hit['_source']['facts']['doc_path']
                spans = hit['_source']['facts']['spans']
                spans = json.loads(spans)
                if doc_id not in self._facts_map:
                    self._facts_map[doc_id] = {}
                if doc_path not in self._facts_map[doc_id]:
                    self._facts_map[doc_id][doc_path] = []
                self._facts_map[doc_id][doc_path].extend(spans)

    def get_facts_map(self):
        """ Returns facts map with doc ids and spans values
        """
        if not self._facts_map:
            self._process_facts()
        return self._facts_map

    def _get_joint_query(self, apply_facts_join = True):
        q = self.combined_query['main']
        facts_map = self.get_facts_map()
        if facts_map and apply_facts_join:
            # Application Joint
            doc_ids = facts_map.keys()
            ids_join = {"ids": {"values": doc_ids}}
            q['query']['bool']['must'].append(ids_join)
        return q

    def search(self, apply_facts=True):
        """ Search
        """
        q = json.dumps(self._get_joint_query(apply_facts_join=apply_facts))
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
            q = json.dumps(self._get_joint_query())
            search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll={3}'.format(es_url, self.index,
                                                                                  self.mapping, time_out)

        response = requests.post(search_url, data=q).json()
        return response

    def get_total_documents(self, apply_facts=True):
        search_url = '{0}/{1}/{2}/_count'.format(es_url, self.index, self.mapping)
        q = json.dumps(self._get_joint_query(apply_facts_join=apply_facts))
        response = requests.post(search_url, data=q).json()
        total = response['count']
        return long(total)
