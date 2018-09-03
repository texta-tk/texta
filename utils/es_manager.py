# -*- coding: utf8 -*-
from __future__ import print_function
import json
import re
import copy
import requests
from collections import defaultdict
import sys
import time
from functools import reduce

if 'django' in sys.modules: # Import django-stuff only if imported from the django application / prevent errors when importing from scripts
    from conceptualiser.models import Concept
    from conceptualiser.models import TermConcept
    from utils.log_manager import LogManager
    from lexicon_miner.models import Word,Lexicon

from utils.query_builder import QueryBuilder
from texta.settings import es_url, es_use_ldap, es_ldap_user, es_ldap_password, FACT_PROPERTIES

# Need to update index.max_inner_result_window to increase
HEADERS = {'Content-Type': 'application/json'}

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

    TEXTA_RESERVED = []
    HEADERS = HEADERS
    #TEXTA_RESERVED = ['texta_facts']

    # Redefine requests if LDAP authentication is used
    if es_use_ldap:
        requests = requests.Session()
        requests.auth = (es_ldap_user, es_ldap_password)
    else:
        requests = requests

    def __init__(self, active_datasets, url=None):
        self.es_url = url if url else es_url
        self.active_datasets = active_datasets
        self.combined_query = None
        self._facts_map = None
        self.es_cache = ES_Cache()
    
    def _stringify_datasets(self):
        indices = [dataset.index for dataset in self.active_datasets]
        index_string = ','.join(indices)
        return index_string

    def update_documents(self, documents, ids):
        data = ''
        
        for i,_id in enumerate(ids):
            data += json.dumps({"update": {"_id": _id, "_type": self.mapping, "_index": self.index}})+'\n'
            data += json.dumps({"doc": documents[i]})+'\n'
        
        response = self.plain_post_bulk(self.es_url, data)
        response = self._update_by_query()
        return response

    def update_mapping_structure(self, new_field, new_field_properties):
        url = '{0}/{1}/_mappings/{2}'.format(self.es_url, self.index ,self.mapping)
        response = self.plain_get(url)
        properties = response[self.index]['mappings'][self.mapping]['properties']
        
        if new_field not in properties:
            properties[new_field] = new_field_properties
        
        if 'texta_facts' not in properties:
            properties['texta_facts'] = FACT_PROPERTIES
        
        properties = {'properties': properties}
        
        response = self.plain_put(url, json.dumps(properties))
        return response

    def _update_by_query(self):
        response = self.plain_post('{0}/{1}/_update_by_query?refresh&conflicts=proceed'.format(self.es_url, self.index))
        return response

    def check_if_field_has_facts(self, sub_fields):
        """ Check if field is associate with facts in Elasticsearch
        """
        doc_type = self.mapping.lower()
        field_path = [s.lower() for s in sub_fields]
        doc_path = '.'.join(field_path)

        request_url = '{0}/{1}/{2}/_count'.format(es_url, self.index, self.mapping)
        base_query = {"query": {"bool": {"filter": {'and': []}}}}
        base_query = {'query': {'nested': {'path': 'texta_facts', 'query': {'bool': {'filter': []}}}}}
        base_query['query']['nested']['query']['bool']['filter'].append({'term': {'texta_facts.doc_path': doc_path}})

        has_facts = self._field_has_facts(request_url, base_query)
        has_fact_str_val = self._field_has_fact_vals(request_url, base_query, 'texta_facts.str_val')
        has_fact_num_val = self._field_has_fact_vals(request_url, base_query, 'texta_facts.num_val')

        return has_facts, has_fact_str_val, has_fact_num_val

    def _field_has_facts(self, url, query):
        query = copy.deepcopy(query)
        query['query']['nested']['query']['bool']['filter'].append({'exists': {'field': 'texta_facts.fact'}})

        query = json.dumps(query)
        response = self.plain_post(url, query)
        return 'count' in response and response['count'] > 0

    def _field_has_fact_vals(self, url, query, value_field_name):
        query = copy.deepcopy(query)
        query['query']['nested']['query']['bool']['filter'].append({'exists': {'field': value_field_name}})
        query = json.dumps(query)

        response = self.requests.post(url, data=query, headers=HEADERS).json()
        return 'count' in response and response['count'] > 0

    def _decode_mapping_structure(self, structure, root_path=list()):
        """ Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []

        for item in structure.items():
            if item[0] in self.TEXTA_RESERVED:
                continue
            if 'properties' in item[1] and 'type' not in item[1]: #added+
                sub_structure = item[1]['properties']
                path_list = root_path[:]
                path_list.append(item[0])
                sub_mapping = self._decode_mapping_structure(sub_structure, root_path=path_list)
                mapping_data.extend(sub_mapping)

            elif 'properties' in item[1] and 'type' in item[1]: # for dealing with facts
                sub_structure = item[1]['properties']
                path_list = root_path[:]
                path_list.append(item[0])
                sub_mapping = [{'path': item[0], 'type': u'string'}]
                mapping_data.extend(sub_mapping)

            else:
                path_list = root_path[:]
                path_list.append(item[0])
                path = '.'.join(path_list)
                data = {'path': path, 'type': item[1]['type']}
                mapping_data.append(data)

        return mapping_data

    @staticmethod
    def plain_get(url):
        return ES_Manager.requests.get(url, headers=HEADERS).json()

    @staticmethod
    def plain_post(url, data=None):
        return ES_Manager.requests.post(url, data=data, headers=HEADERS).json()

    @staticmethod
    def plain_post_bulk(url, data):
        return ES_Manager.requests.post('{0}/_bulk'.format(url), data=data, headers=HEADERS).json()

    @staticmethod
    def plain_put(url, data=None):
        return ES_Manager.requests.put(url, data=data, headers=HEADERS).json()

    @staticmethod
    def plain_delete(url, data=None):
        return ES_Manager.requests.delete(url, data=data, headers=HEADERS).json()

    @staticmethod
    def plain_search(es_url, dataset, mapping, query):
        return ES_Manager.requests.post(es_url+'/'+dataset+'/'+mapping+'/_search',data=json.dumps(query), headers=HEADERS).json()

    @staticmethod
    def plain_multisearch(es_url, dataset, mapping, data):
        responses = ES_Manager.requests.post(es_url+'/'+dataset+'/'+mapping+'/_msearch',data='\n'.join(data)+'\n', headers=HEADERS).json()
        if 'responses' in responses:
            return responses['responses']
        else:
            return []

    @staticmethod
    def plain_scroll(es_url, dataset, mapping, query, expiration_str='1m'):
        return ES_Manager.requests.post(es_url+'/'+dataset+'/'+mapping+'/_search?scroll='+expiration_str, data=query, headers=HEADERS).json()

    @staticmethod
    def delete_index(index):
        url = '{0}/{1}'.format(es_url, index)
        ES_Manager.requests.delete(url, headers=HEADERS)
        return True

    def get_mapped_fields(self):
        """ Get flat structure of fields from Elasticsearch mappings
        """
        mapping_data = []
        
        if self.active_datasets:
            index_string = self._stringify_datasets()          
            url = '{0}/{1}'.format(es_url,index_string)
            
            for index_properties in self.plain_get(url).values():
                for mapping in index_properties['mappings']:
                    mapping_structure = index_properties['mappings'][mapping]['properties']
                    mapping_data+=self._decode_mapping_structure(mapping_structure)

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

    def build(self, es_params):
        self.combined_query = QueryBuilder(es_params).query

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
        search_url = '{0}/{1}/_search'.format(es_url, self._stringify_datasets())
        response = self.plain_post(search_url, q)
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
        response = requests.post(search_url, data=q, headers=HEADERS).json()

        scroll_id = response['_scroll_id']
        l = response['hits']['total']

        # Delete initial response
        data = self.process_bulk(response['hits']['hits'])
        delete_url = '{0}/{1}/{2}/_bulk'.format(es_url, self.index, self.mapping)
        deleted = requests.post(delete_url, data=data, headers=HEADERS)
        while l > 0:
            response = self.scroll(scroll_id=scroll_id, time_out=time_out)
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            data = self.process_bulk(response['hits']['hits'])
            delete_url = '{0}/{1}/{2}/_bulk'.format(es_url, self.index, self.mapping)
            deleted = requests.post(delete_url, data=data, headers=HEADERS)

        return True

    def scroll(self, scroll_id=None, time_out='1m', id_scroll=False, field_scroll=False, size=100, match_all=False):
        """ Search and Scroll
        """
        if scroll_id:
            q = json.dumps({"scroll": time_out, "scroll_id": scroll_id})
            search_url = '{0}/_search/scroll'.format(es_url)
        else:
            if match_all == True:
                q = {}
            else:
                q = self.combined_query['main']
            q['size'] = size
            search_url = '{0}/{1}/{2}/_search?scroll={3}'.format(es_url, self.index, self.mapping, time_out)

            if id_scroll:
                q['_source'] = 'false'
            elif field_scroll:
                q['_source'] = field_scroll

            q = json.dumps(q)

        response = self.requests.post(search_url, data=q, headers=HEADERS).json()
        return response

    def get_total_documents(self):
        q = self.combined_query['main']
        total = self.plain_search(self.es_url, self.index, self.mapping, q)['hits']['total']
        return int(total)

    @staticmethod
    def get_indices():
        url = '{0}/_cat/indices?format=json'.format(es_url)
        response = ES_Manager.requests.get(url, headers=HEADERS).json()
        return sorted([{'index':i['index'],'status':i['status'],'docs_count':i['docs.count'],'store_size':i['store.size']} for i in response], key=lambda k: k['index']) # NEW PY REQUIREMENT

    @staticmethod
    def get_mappings(index):
        url = '{0}/{1}'.format(es_url, index)
        response = ES_Manager.requests.get(url, headers=HEADERS).json()

        return sorted([mapping for mapping in response[index]['mappings']])

    @staticmethod
    def open_index(index):
        url = '{0}/{1}/_open'.format(es_url, index)
        response = ES_Manager.requests.post(url, headers=HEADERS).json()
        return response

    @staticmethod
    def close_index(index):
        url = '{0}/{1}/_close'.format(es_url, index)
        response = ES_Manager.requests.post(url, headers=HEADERS).json()
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
        response = requests.post(url, data=json.dumps(query), headers=HEADERS).json()
        aggs = response["aggregations"]
        return aggs["min_date"]["value_as_string"],aggs["max_date"]["value_as_string"]

    def clear_readonly_block(self):
        '''changes read_only_allow_delete to False'''
        data = {"index":{"blocks":{"read_only_allow_delete":"false"}}}
        url = "{0}/{1}/_settings".format(self.es_url, self.index)
        response = self.plain_put(url, json.dumps(data))
        return response

