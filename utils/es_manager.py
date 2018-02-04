# -*- coding: utf8 -*-
import json
import re
import copy
import requests
from collections import defaultdict
import sys
import time

if 'django' in sys.modules: # Import django-stuff only if imported from the django application / prevent errors when importing from scripts
    from conceptualiser.models import Concept
    from conceptualiser.models import TermConcept
    from utils.log_manager import LogManager
    from lm.models import Word,Lexicon

from texta.settings import es_url, es_use_ldap, es_ldap_user, es_ldap_password

# Need to update index.max_inner_result_window to increase
INNER_HITS_MAX_SIZE = 100

headers = {'Content-Type': 'application/json'}

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
    TEXTA_RESERVED = ['texta_facts']
    
    # Redefine requests if LDAP authentication is used
    if es_use_ldap:
        requests = requests.Session()
        requests.auth = (es_ldap_user, es_ldap_password)
    else:
        requests = requests

    def __init__(self, index, mapping, url=None):
        self.es_url = url if url else es_url
        self.index = index
        self.mapping = mapping
        self.combined_query = None
        self._facts_map = None
        self.es_cache = ES_Cache()

    def check_if_field_has_facts(self, sub_fields):
        """ Check if field is associate with facts in Elasticsearch
        """
        doc_type = self.mapping.lower()
        field_path = [s.lower() for s in sub_fields]
        doc_path = '.'.join(field_path)

        request_url = '{0}/{1}/{2}/_count'.format(es_url, self.index, self.mapping)
        base_query = {"query": {"bool": {"filter": {'and': []}}}}
        base_query = {'query': {'nested': {'path': 'texta_facts', 'query': {'bool': {'filter': []}}}}}  # {'match':{'texta_facts.fact':'superhero'}}}}}
        #base_query['query']['bool']['filter']['and'].append({"term": {'facts.doc_type': doc_type}})
        #base_query['query']['bool']['filter']['and'].append({"term": {'facts.doc_path': doc_path}})
        base_query['query']['nested']['query']['bool']['filter'].append({'term': {'texta_facts.doc_path': doc_path}})

        has_facts = self._field_has_facts(request_url, base_query)
        has_fact_str_val = self._field_has_fact_vals(request_url, base_query, 'texta_facts.str_val')
        has_fact_num_val = self._field_has_fact_vals(request_url, base_query, 'texta_facts.num_val')

        return has_facts, has_fact_str_val, has_fact_num_val

    def _field_has_facts(self, url, query):
        query = copy.deepcopy(query)
        query['query']['nested']['query']['bool']['filter'].append({'exists': {'field': 'texta_facts.fact'}})

        query = json.dumps(query)
        response = self.requests.post(url, data=query, headers=headers).json()

        return 'count' in response and response['count'] > 0

    def _field_has_fact_vals(self, url, query, value_field_name):
        query = copy.deepcopy(query)
        query['query']['nested']['query']['bool']['filter'].append({'exists': {'field': value_field_name}})
        query = json.dumps(query)

        response = self.requests.post(url, data=query, headers=headers).json()
        return 'count' in response and response['count'] > 0

    def _decode_mapping_structure(self, structure, root_path=list()):
        """ Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []

        for item in structure.items():
            if item[0] in self.TEXTA_RESERVED:
                continue
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

    @staticmethod
    def plain_get(self, url):
        return ES_Manager.requests.get(url, headers=headers).json()
    
    @staticmethod
    def plain_post(url, data=None):
        return ES_Manager.requests.post(url, data=data, headers=headers).json()
    
    @staticmethod
    def plain_put(url, data=None):
        return ES_Manager.requests.put(url, data=data, headers=headers).json()
    
    @staticmethod
    def plain_delete(url, data=None):
        return ES_Manager.requests.delete(url, data=data, headers=headers).json()
    
    @staticmethod
    def plain_search(es_url, dataset, mapping, query):
        return ES_Manager.requests.post(es_url+'/'+dataset+'/'+mapping+'/_search',data=json.dumps(query), headers=headers).json()
    
    @staticmethod
    def plain_multisearch(es_url, dataset, mapping, data):
        return ES_Manager.requests.post(es_url+'/'+dataset+'/'+mapping+'/_msearch',data='\n'.join(data)+'\n', headers=headers).json()['responses']
    
    @staticmethod
    def plain_scroll(es_url, dataset, mapping, query, expiration_str='1m'):
        return ES_Manager.requests.post(es_url+'/'+dataset+'/'+mapping+'/_search?scroll='+expiration_str, data=query, headers=headers).json()

    def get_mapped_fields(self):
        """ Get flat structure of fields from Elasticsearch mapping
        """
        mapping_data = []
        if self.index:
            mapping_structure = self.requests.get(es_url+'/'+self.index, headers=headers).json()[self.index]['mappings'][self.mapping]['properties']
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
            if item.startswith('daterange'):
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
        fact_val_constraint_keys = {u'type':None, u'val':None, u'op':None}
        for item in es_params:
            if 'fact' in item:
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if len(item) > 3:
                    fact_val_constraint_keys[second_part] = None
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]

        ES_Manager._remove_fact_val_fields(_constraints, fact_val_constraint_keys)

        return _constraints

    @staticmethod
    def _remove_fact_val_fields(constraints, fact_val_keys):
        keys_to_remove = [key for key in fact_val_keys if key in constraints]
        for key in keys_to_remove:
            del constraints[key]

    @staticmethod
    def _get_fact_val_constraints(es_params):
        constraints = defaultdict(lambda: {'constraints': defaultdict(dict)})
        for item in es_params:
            if 'fact_constraint' in item:
                key_parts = item.split('_')
                specifier, field_id = key_parts[2], key_parts[3]

                if specifier == 'type':
                    constraints[field_id]['type'] = es_params[item]
                else:
                    constraint_id = key_parts[4]
                    specifier_map = {'op': 'operator', 'val': 'value'}
                    constraints[field_id]['constraints'][constraint_id][specifier_map[specifier]] = es_params[item]
            elif 'fact_txt' in item:
                key_parts = item.split('_')

                if len(key_parts) == 3:  # Normal fact constraint
                    continue

                field_id, constraint_id = key_parts[2], key_parts[3]
                constraints[field_id]['constraints'][constraint_id]['name'] = es_params[item]
            elif 'fact_operator' in item:
                field_id = item.rsplit('_', 1)[1]
                constraints[field_id]['operator'] = es_params[item]
            elif 'fact_field' in item:
                field_id = item.rsplit('_', 1)[1]
                constraints[field_id]['field'] = es_params[item]

        constraints = dict(constraints)
        for constraint in constraints.values():
            constraint['constraints'] = dict(constraint['constraints'])

        ES_Manager._remove_non_fact_val_fields(constraints)
        ES_Manager._convert_fact_vals(constraints)

        return constraints

    @staticmethod
    def _remove_non_fact_val_fields(constraints):
        fields_to_remove = []
        for field_id in constraints:
            if len(constraints[field_id]['constraints']) == 0:
                fields_to_remove.append(field_id)
        for field_id in fields_to_remove:
            del constraints[field_id]

    @staticmethod
    def _convert_fact_vals(constraints):
        for constraint in constraints.values():
            if constraint['type'] == 'num':
                for sub_constraint in constraint['constraints'].values():
                    sub_constraint['value'] = float(sub_constraint['value'])

    @staticmethod
    def _get_list_synonyms(query_string):
        """ check if string is a concept or lexicon identifier
        """
        synonyms = []
        concept = re.search('^@C(\d)+-', query_string)
        lexicon = re.search('^@L(\d)+-', query_string)
        
        if concept:
            concept_id = int(concept.group()[2:-1])
            for term in TermConcept.objects.filter(concept=Concept.objects.get(pk=concept_id)):
                synonyms.append(term.term.term)
        elif lexicon:
            lexicon_id = int(lexicon.group()[2:-1])
            for word in Word.objects.filter(lexicon=Lexicon.objects.get(pk=lexicon_id)):
                synonyms.append(word.wrd)
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
        fact_val_constraints = self._get_fact_val_constraints(es_params)

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
        for field_id, fact_constraint in fact_constraints.items():
            _combined_query['main']['query']['bool']['must'].append({'nested': {'path': 'texta_facts', 'query':{'bool': {'must': []}}}})
            fact_query = _combined_query['main']['query']['bool']['must'][-1]['nested']['query']['bool']['must']

            fact_field = fact_constraint['fact_field'] if 'fact_field' in fact_constraint else ''
            fact_txt = fact_constraint['fact_txt'] if 'fact_txt' in fact_constraint else ''
            fact_operator = fact_constraint['fact_operator'] if 'fact_operator' in fact_constraint else ''
            query_strings = [s.replace('\r', '') for s in fact_txt.split('\n')]
            query_strings = [s.lower() for s in query_strings if s]
            sub_queries = []
            # Add facts query to search in facts mapping
            fact_queries = []

            #fact_query.append({'match_phrase': {'texta_facts.fact': fact_field}})

            if query_strings:

                _combined_query['main']['query']['bool']['must'].append({'bool': {fact_operator: []}})
                fact_query = _combined_query['main']['query']['bool']['must'][-1]['bool'][fact_operator]


                for string_id, query_string in enumerate(query_strings):
                    fact_query.append(
                        {
                            'nested': {
                                'path': 'texta_facts',
                                'inner_hits': {
                                    'name': 'fact_' + str(field_id) + '_' + str(string_id),
                                    'size': INNER_HITS_MAX_SIZE
                                },
                                'query': {
                                    'bool': {
                                        'must': []
                                    }
                                }
                            }
                        }
                    )
                    nested_query = fact_query[-1]['nested']['query']['bool']['must']

                    nested_query.append({'match': {'texta_facts.doc_path': fact_field.lower()}})
                    nested_query.append({'match': {'texta_facts.fact': query_string}})

        for field_id, fact_val_constraint in fact_val_constraints.items():
            fact_operator = fact_val_constraint['operator']
            fact_field = fact_val_constraint['field']
            val_type = fact_val_constraint['type']

            _combined_query['main']['query']['bool']['must'].append({'bool': {fact_operator: []}})
            fact_val_query = _combined_query['main']['query']['bool']['must'][-1]['bool'][fact_operator]

            for constraint_id, value_constraint in fact_val_constraint['constraints'].items():
                fact_name = value_constraint['name']
                fact_value = value_constraint['value']
                fact_val_operator = value_constraint['operator']

                fact_val_query.append(
                    {
                        'nested': {
                            'path': 'texta_facts',
                            'inner_hits': {
                                'name': 'fact_val_'+str(field_id)+'_'+str(constraint_id),
                                'size': INNER_HITS_MAX_SIZE
                            },
                            'query': {
                                'bool': {
                                    'must': []
                                }
                            }
                        }
                    }
                )
                nested_query = fact_val_query[-1]['nested']['query']['bool']['must']
                nested_query.append({'match': {'texta_facts.fact': fact_name}})
                nested_query.append({'match': {'texta_facts.doc_path': fact_field}})

                if val_type == 'str':
                    if fact_val_operator == '=':
                        nested_query.append({'match': {'texta_facts.str_val': fact_value}})
                    elif fact_val_operator == '!=':
                        nested_query = fact_val_query[-1]['nested']['query']['bool']
                        nested_query['must_not'] = [{'match': {'texta_facts.str_val': fact_value}}]

                elif val_type == 'num':
                    if fact_val_operator == '=':
                        nested_query.append({'term': {'texta_facts.num_val': fact_value}})
                    elif fact_val_operator == '!=':
                        nested_query = fact_val_query[-1]['nested']['query']['bool']
                        nested_query['must_not'] = [{'match': {'texta_facts.num_val': fact_value}}]
                    else:
                        operator = {'<': 'lt', '<=': 'lte', '>': 'gt', '>=': 'gte'}[fact_val_operator]
                        nested_query.append({'range': {'texta_facts.num_val': {operator: fact_value}}})


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
        search_url = '{0}/{1}/{2}/_search?scroll=1m&size=500'.format(es_url, self.index, self.TEXTA_MAPPING)
        response = self.requests.post(search_url, data=q, headers=headers).json()
        scroll_id = json.dumps({'scroll_id':response['_scroll_id']})
        total_msg = response['hits']['total']
        count_limit = 0
        while 'hits' in response and 'hits' in response['hits'] and response['hits']['hits'] and (count_limit < max_size):
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
            response = self.requests.post(scroll_url, data=scroll_id, headers=headers).json()

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

    def search(self):
        """ Search
        """
        q = json.dumps(self.combined_query['main'])
        print q
        search_url = '{0}/{1}/{2}/_search'.format(es_url, self.index, self.mapping)
        response = self.requests.post(search_url, data=q, headers=headers).json()
        print response
        return response

    def process_bulk(self,hits):
        data = ''
        for hit in hits:
            data += json.dumps({"delete":{"_index":self.index,"_type":self.mapping,"_id":hit['_id']}})+'\n'
        return data

    def delete(self, time_out='1m'):
        """ Deletes the selected rows
        """

        q = json.dumps(self.combined_query['main'])
        search_url = '{0}/{1}/{2}/_search?scroll={3}'.format(es_url, self.index, self.mapping, time_out)
        response = requests.post(search_url, data=q, headers=headers).json()

        scroll_id = response['_scroll_id']
        l = response['hits']['total']
    
        while l > 0:
            search_url = '{0}/_search/scroll?scroll={1}'.format(es_url,time_out)
            response = requests.post(search_url, data=scroll_id, headers=headers).json()
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
 
            data = self.process_bulk(response['hits']['hits'])
            delete_url = '{0}/{1}/{2}/_bulk'.format(es_url, self.index, self.mapping)
            deleted = requests.post(delete_url, data=data, headers=headers)

        return True

    def scroll(self, scroll_id=None, time_out='1m', id_scroll=False, field_scroll=False, size=100):
        """ Search and Scroll
        """
        if scroll_id:
            q = json.dumps({"scroll": time_out, "scroll_id": scroll_id})
            search_url = '{0}/_search/scroll'.format(es_url)
        else:
            q = self.combined_query['main']
            q['size'] = size
            search_url = '{0}/{1}/{2}/_search?scroll={3}'.format(es_url, self.index, self.mapping, time_out)
            
            if id_scroll:
                q['_source'] = 'false'
            elif field_scroll:
                q['_source'] = field_scroll

            q = json.dumps(q)

        response = self.requests.post(search_url, data=q, headers=headers).json()
        return response

    # THIS SHOULD NOT BE NECESSARY
    #def scroll_all_match(self, scroll_id=None, time_out='1m', id_scroll=False):
    #    """ Search and Scroll in a match all search
    #    """
    #    if scroll_id:
    #        q = json.dumps({"scroll": time_out, "scroll_id": scroll_id})
    #        search_url = '{0}/_search/scroll'.format(es_url)
    #    else:
    #        q = json.dumps({'query': {"match_all": {}}})
    #        if id_scroll:
    #            search_url = '{0}/{1}/{2}/_search?scroll={3}&fields='.format(es_url, self.index, self.mapping, time_out)
    #        else:
    #            search_url = '{0}/{1}/{2}/_search?scroll={3}'.format(es_url, self.index, self.mapping, time_out)
    #
    #    response = self.requests.post(search_url, data=q, headers=headers).json()
    #    return response

    def get_total_documents(self):
        search_url = '{0}/{1}/{2}/_count'.format(es_url, self.index, self.mapping)
        q = json.dumps(self.combined_query['main'])
        response = self.requests.post(search_url, data=q, headers=headers).json()
        total = response['count']
        return long(total)

    def _get_facts_structure_agg(self):
        query = {"query": {"term": {"facts.doc_type": self.mapping.lower()}}}
        aggregations = {"fact": {'terms': {"field": 'facts.fact'},
                                 'aggs': {"doc_path": {"terms": {"field": 'facts.doc_path'}}}}}
        query['aggs'] = aggregations
        query = json.dumps(query)
        request_url = '{0}/{1}/{2}/_search?_source=false'.format(es_url, self.index, self.TEXTA_MAPPING)
        response = self.requests.get(request_url, data=query, headers=headers).json()
        agg = response['aggregations']
        facts_agg_structure = {}
        for fact in agg['fact']['buckets']:
            fact_name = fact['key']
            if fact_name not in facts_agg_structure:
                facts_agg_structure[fact_name] = set()
            for t in fact['doc_path']['buckets']:
                doc_path = t['key']
                facts_agg_structure[fact_name].add(doc_path)
        return facts_agg_structure

    def _get_facts_structure_no_agg(self):
        facts_structure = {}
        base_url = '{0}/{1}/{2}/_search?scroll=1m&size=1000'
        search_url = base_url.format(es_url, self.index, self.TEXTA_MAPPING)
        query = {"query": {"term": {"facts.doc_type": self.mapping.lower()}}}
        query = json.dumps(query)
        response = self.requests.post(search_url, data=query, headers=headers).json()
        scroll_id = response['_scroll_id']
        total = response['hits']['total']
        while total > 0:
            response = self.requests.post('{0}/_search/scroll?scroll=1m'.format(es_url), data=scroll_id, headers=headers).json()
            total = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            for hit in response['hits']['hits']:
                fact = hit['_source']['facts']['fact']
                doc_path = hit['_source']['facts']['doc_path']
                if fact not in facts_structure:
                    facts_structure[fact] = set()
                facts_structure[fact].add(doc_path)
        return facts_structure

    def get_facts_structure(self):
        """ Get facts structure
            Returns: dictionary in the form {fact: [set of fields]}
        """
        logger = LogManager(__name__, 'ES MANAGER')
        facts_structure = {}
        no_aggs = False
        try:
            facts_structure = self._get_facts_structure_agg()
        except KeyError:
            no_aggs = True

        if no_aggs:
            facts_structure = self._get_facts_structure_no_agg()
            logger.error('facts_error', msg='Could not use aggregation in facts structure')

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

        search_param = 'scroll=1m&size=1000'
        search_url = '{0}/{1}/{2}/_search?{3}'.format(es_url, self.index, self.TEXTA_MAPPING, search_param)
        response = self.requests.post(search_url, data=query, headers=headers).json()
        scroll_id = response['_scroll_id']
        total = response['hits']['total']
        facts = {}
        while total > 0:
            response = self.requests.post('{0}/_search/scroll?scroll=1m'.format(es_url), data=scroll_id, headers=headers).json()
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

    @staticmethod
    def get_indices():
        url = '{0}/_cat/indices?format=json'.format(es_url)
        response = ES_Manager.requests.get(url, headers=headers).json()
        
        return sorted([{'index':i['index'],'status':i['status'],'docs_count':i['docs.count'],'store_size':i['store.size']} for i in response])
    
    @staticmethod
    def get_mappings(index):
        url = '{0}/{1}'.format(es_url, index)
        response = ES_Manager.requests.get(url, headers=headers).json()
        
        return sorted([mapping for mapping in response[index]['mappings']])

    @staticmethod
    def open_index(index):
        url = '{0}/{1}/_open'.format(es_url, index)
        response = ES_Manager.requests.post(url, headers=headers).json()
        return response

    @staticmethod
    def close_index(index):
        url = '{0}/{1}/_close'.format(es_url, index)
        response = ES_Manager.requests.post(url, headers=headers).json()
        return response
    
    def merge_combined_query_with_query_dict(self, query_dict):
        """ Merge the current query with the provided query
            Merges the dictonaries entry-wise and uses conjunction in boolean queries, where needed. Alters the current query in place.
        """
        
        try:
            query_dict['main']['query']['bool']
        except:
            raise Exception('Incompatible queries.')
        
        if 'must' in query_dict['main']['query']['bool'] and query_dict['main']['query']['bool']['must']:
            for constraint in query_dict['main']['query']['bool']['must']:
                self.combined_query['main']['query']['bool']['must'].append(constraint)
        if 'should' in query_dict['main']['query']['bool'] and query_dict['main']['query']['bool']['should']:
            if len(query_dict['main']['query']['bool']['should']) > 1:
                target_list = []
                self.combined_query['main']['query']['bool']['must'].append({'or':target_list})
            else:
                target_list = self.combined_query['main']['query']['bool']['must']
            for constraint in query_dict['main']['query']['bool']['should']:
                target_list.append(constraint)
        if 'must_not' in query_dict['main']['query']['bool'] and query_dict['main']['query']['bool']['must_not']:
            for constraint in query_dict['main']['query']['bool']['must_not']:
                self.combined_query['main']['query']['bool']['must_not'].append(constraint)

    def more_like_this_search(self,fields,stopwords=[],docs_accepted=[],docs_rejected=[],handle_negatives='ignore'):

        # Get ids from basic search
        docs_search = self._scroll_doc_ids()
        # Combine ids from basic search and mlt search
        docs_combined = list(set().union(docs_search,docs_accepted))

        mlt = {
            "more_like_this": {
                "fields" : fields,
                "like" : self._add_doc_ids_to_query(docs_combined),
                "min_term_freq" : 1,
                "max_query_terms" : 12,
            }
        }

        if stopwords:
            mlt["more_like_this"]["stop_words"] = stopwords

        highlight_fields = {}
        for field in fields:
            highlight_fields[field] = {}

        query = {
            "query":{
                "bool":{
                    "must":[mlt]
                }
            },
            "size":10,
            "highlight" : {
                "pre_tags" : ["<b>"],
                "post_tags" : ["</b>"],
                "fields" : highlight_fields
            }
        }

        if docs_rejected:
            if handle_negatives == 'unlike':
                mlt["more_like_this"]["unlike"] = self._add_doc_ids_to_query(docs_rejected)
            elif handle_negatives == 'ignore':
                rejected = [{'ids':{'values':docs_rejected}}]
                query["query"]["bool"]["must_not"] = rejected

        response = ES_Manager.plain_search(self.es_url, self.index, self.mapping, query)
        
        return response


    def _add_doc_ids_to_query(self,ids):
        return [{"_index" : self.index, "_type" : self.mapping, "_id" : id} for id in ids]


    def _scroll_doc_ids(self,limit=500):
        ids = []
        
        response = self.scroll(id_scroll=True, size=100)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        while hits:
            hits = response['hits']['hits']
            for hit in hits:
                ids.append(hit['_id'])
                if len(ids) == limit:
                    return ids
            response = self.scroll(scroll_id=scroll_id)
            scroll_id = response['_scroll_id']

        return ids


    def perform_queries(self,queries):
        response = ES_Manager.plain_multisearch(self.es_url, self.index, self.mapping, queries)
        return response      


    def get_extreme_dates(self,field):
        query = {"aggs":{"max_date":{"max":{"field":field}},"min_date":{"min":{"field":field}}}}
        url = "{0}/{1}/{2}/_search".format(self.es_url, self.index, self.mapping)
        response = requests.post(url, data=json.dumps(query), headers=headers).json()
        aggs = response["aggregations"]
        return aggs["min_date"]["value_as_string"],aggs["max_date"]["value_as_string"]
        
