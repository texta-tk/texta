# -*- coding: utf8 -*-
from __future__ import print_function
import json
import copy
from pprint import pprint
from typing import List, Dict, Any

import requests
from functools import reduce
from utils.generic_helpers import find_key_recursivly
import datetime

from utils.query_builder import QueryBuilder
from texta.settings import es_url, es_use_ldap, es_ldap_user, es_ldap_password, FACT_PROPERTIES, date_format, es_prefix

# Need to update index.max_inner_result_window to increase
HEADERS = {'Content-Type': 'application/json'}


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ES_Manager:
    """ Manage Elasticsearch operations and interface
    """

    HEADERS = HEADERS
    TEXTA_RESERVED = ['texta_facts']

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

    def stringify_datasets(self) -> str:
        """
        Return a comma separated string of index names for
        Elasticsearch multi-index operations.
        :return:
        """
        indices = [dataset.index for dataset in self.active_datasets]
        index_string = ','.join(indices)
        return index_string

    def bulk_post_update_documents(self, documents, ids):
        """Do both plain_post_bulk and _update_by_query"""
        data = ''

        for i, _id in enumerate(ids):
            data += json.dumps({"update": {"_id": _id, "_index": self.stringify_datasets()}}) + '\n'
            data += json.dumps({"doc": documents[i]}) + '\n'

        response = self.plain_post_bulk(self.es_url, data)
        response = self._update_by_query()
        return response

    def bulk_post_documents(self, documents, ids):
        """Do just plain_post_bulk"""
        data = ''

        for i, _id in enumerate(ids):
            data += json.dumps({"update": {"_id": _id, "_index": self.stringify_datasets()}}) + '\n'
            data += json.dumps({"doc": documents[i]}) + '\n'

        response = self.plain_post_bulk(self.es_url, data)
        return response

    def update_documents(self):
        """Do just _update_by_query"""
        response = self._update_by_query()
        return response

    def update_mapping_structure(self, new_field, new_field_properties):
        url = '{0}/{1}/_mappings/'.format(self.es_url, self.stringify_datasets())
        response = self.plain_get(url)

        for index in self.stringify_datasets().split(','):
            for mapping in response[index]['mappings'].keys():
                properties = response[index]['mappings'][mapping]['properties']

                if new_field not in properties:
                    properties[new_field] = new_field_properties

                if 'texta_facts' not in properties:
                    properties['texta_facts'] = FACT_PROPERTIES

                properties = {'properties': properties}

                response = self.plain_put(url, json.dumps(properties))

    def _update_by_query(self):
        response = self.plain_post('{0}/{1}/_update_by_query?refresh&conflicts=proceed'.format(self.es_url, self.stringify_datasets()))
        return response

    def _decode_mapping_structure(self, structure, root_path=list(), nested_layers=list()):
        """ Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []

        for k, v in structure.items():
            # deal with fact field
            if 'properties' in v and k in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = [{'path': k, 'type': 'text'}]
                mapping_data.extend(sub_mapping)

            # deal with object & nested structures 
            elif 'properties' in v and k not in self.TEXTA_RESERVED:
                sub_structure = v['properties']

                # add layer path
                nested_layers_updated = nested_layers[:]
                if 'type' in v:
                    if v['type'] == 'nested':
                        nested_layers_updated.append(k)

                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = self._decode_mapping_structure(sub_structure, root_path=path_list, nested_layers=nested_layers_updated)
                mapping_data.extend(sub_mapping)

            else:
                path_list = root_path[:]
                path_list.append(k)
                path = '.'.join(path_list)
                data = {'path': path, 'type': v['type'], 'nested_layers': nested_layers}
                mapping_data.append(data)

        return mapping_data

    @staticmethod
    def plain_get(url) -> dict:
        return ES_Manager.requests.get(url, headers=HEADERS).json()

    @staticmethod
    def plain_post(url, data=None) -> dict:
        return ES_Manager.requests.post(url, data=data, headers=HEADERS).json()

    @staticmethod
    def plain_post_bulk(url, data) -> dict:
        return ES_Manager.requests.post('{0}/_bulk'.format(url), data=data, headers=HEADERS).json()

    @staticmethod
    def plain_put(url, data=None) -> dict:
        return ES_Manager.requests.put(url, data=data, headers=HEADERS).json()

    @staticmethod
    def plain_delete(url, data=None) -> dict:
        return ES_Manager.requests.delete(url, data=data, headers=HEADERS).json()

    @staticmethod
    def plain_search(es_url, datasets, query) -> dict:
        return ES_Manager.requests.post(es_url + '/' + datasets + '/_search', data=json.dumps(query), headers=HEADERS).json()

    @staticmethod
    def plain_multisearch(es_url, data):
        responses = ES_Manager.requests.post(es_url + '/_msearch', data='\n'.join(data) + '\n', headers=HEADERS).json()
        if 'responses' in responses:
            return responses['responses']
        else:
            return []

    @staticmethod
    def plain_scroll(es_url, dataset, mapping, query, expiration_str='1m'):
        url = es_url + '/' + dataset + '/' + mapping + '/_search?scroll=' + expiration_str
        return ES_Manager.requests.post(url, data=query, headers=HEADERS).json()

    @staticmethod
    def delete_index(index):
        url = '{0}/{1}'.format(es_url, index)
        ES_Manager.requests.delete(url, headers=HEADERS)
        return True

    def get_fields_with_facts(self):
        queries = []

        fact_types_with_queries = {
            'fact': {'match_all': {}},
            'fact_str': {'nested': {'path': 'texta_facts', 'query': {'exists': {'field': 'texta_facts.str_val'}}, 'inner_hits': {}}},
            'fact_num': {'nested': {'path': 'texta_facts', 'query': {'exists': {'field': 'texta_facts.num_val'}}, 'inner_hits': {}}}
        }

        for fact_type, query in fact_types_with_queries.items():
            for active_dataset in self.active_datasets:
                aggs = {
                    fact_type: {
                        "nested": {"path": "texta_facts"},
                        "aggs": {
                            fact_type: {
                                'terms': {"field": "texta_facts.doc_path", "size": 1, 'order': {'documents.doc_count': 'desc'}},
                                "aggs": {
                                    "documents": {"reverse_nested": {}}
                                }
                            }
                        }
                    }
                }

                query_header = {'index': active_dataset.index, 'mapping': active_dataset.mapping}
                query_body = {'query': query, 'aggs': aggs}
                queries.append(json.dumps(query_header))
                queries.append(json.dumps(query_body))

        responses = self.plain_multisearch(es_url, queries)

        fields_with_facts = {'fact': [], 'fact_str': [], 'fact_num': []}

        for response in responses:
            if 'aggregations' in response:
                aggregations = response['aggregations']
                for fact_type in list(fields_with_facts.keys()):
                    if fact_type in aggregations:
                        second_agg = aggregations[fact_type]
                        if fact_type in second_agg:
                            buckets = second_agg[fact_type]['buckets']
                            fields_with_facts[fact_type] += [a['key'] for a in buckets]

        return fields_with_facts

    @staticmethod
    def _parse_buckets(response, key):
        fact_count = response['aggregations'][key]
        if key in fact_count:
            return [bucket['key'] for bucket in fact_count[key]['buckets']]
        return []

    def get_mapped_fields(self):
        """ Get flat structure of fields from Elasticsearch mappings
        """
        mapping_data = {}

        if self.active_datasets:
            index_string = self.stringify_datasets()
            url = '{0}/{1}'.format(es_url, index_string)

            for index_name, index_properties in self.plain_get(url).items():
                for mapping in index_properties['mappings']:
                    mapping_structure = index_properties['mappings'][mapping]['properties']
                    decoded_mapping_structure = self._decode_mapping_structure(mapping_structure)

                    for field_mapping in decoded_mapping_structure:
                        field_mapping_json = json.dumps(field_mapping)
                        if field_mapping_json not in mapping_data:
                            mapping_data[field_mapping_json] = []

                        dataset_info = {'index': index_name, 'mapping': mapping}
                        if dataset_info not in mapping_data[field_mapping_json]:
                            mapping_data[field_mapping_json].append({'index': index_name, 'mapping': mapping})

        return mapping_data

    def get_column_names(self, include_reserved_fields=False) -> list:
        """ Get Column names from flat mapping structure
            Returns: sorted list of names
        """
        mapped_fields = self.get_mapped_fields()

        if include_reserved_fields is False:
            mapped_fields = [json.loads(field_data) for field_data in list(mapped_fields.keys())]
            column_names = [c['path'] for c in mapped_fields if not self._is_reserved_field(c['path'])]
            column_names.sort()
        else:
            mapped_fields = [json.loads(field_data) for field_data in list(mapped_fields.keys())]
            column_names = [c['path'] for c in mapped_fields]
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

    def search(self):
        """ Search
        """
        q = json.dumps(self.combined_query['main'])
        search_url = '{0}/{1}/_search'.format(es_url, self.stringify_datasets())
        response = self.plain_post(search_url, q)
        return response

    def process_bulk(self, hits):
        data = ''
        for hit in hits:
            data += json.dumps({"delete": {"_index": self.stringify_datasets(), "_id": hit['_id']}}) + '\n'
        return data

    def delete(self, time_out='1m'):
        """ Deletes the selected rows
        """

        q = json.dumps(self.combined_query['main'])
        search_url = '{0}/{1}/_search?scroll={2}'.format(es_url, self.stringify_datasets(), time_out)
        response = requests.post(search_url, data=q, headers=HEADERS).json()

        scroll_id = response['_scroll_id']
        total_hits = response['hits']['total']

        # Delete initial response
        data = self.process_bulk(response['hits']['hits'])
        delete_url = '{0}/{1}/_bulk'.format(es_url, self.stringify_datasets())
        deleted = requests.post(delete_url, data=data, headers=HEADERS)

        while total_hits > 0:
            response = self.scroll(scroll_id=scroll_id, time_out=time_out)
            total_hits = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            data = self.process_bulk(response['hits']['hits'])
            delete_url = '{0}/{1}/_bulk'.format(es_url, self.stringify_datasets())
            deleted = requests.post(delete_url, data=data, headers=HEADERS)

        return True

    def scroll(self, scroll_id=None, time_out='1m', id_scroll=False, field_scroll=False, size=100, match_all=False):
        """ Search and Scroll
        """
        if scroll_id:
            q = json.dumps({"scroll": time_out, "scroll_id": scroll_id})
            search_url = '{0}/_search/scroll'.format(es_url)
        else:
            if match_all is True:
                q = {}
            else:
                q = self.combined_query['main']
            q['size'] = size
            search_url = '{0}/{1}/_search?scroll={2}'.format(es_url, self.stringify_datasets(), time_out)

            if id_scroll:
                q['_source'] = 'false'
            elif field_scroll:
                q['_source'] = field_scroll

            q = json.dumps(q)

        response = self.requests.post(search_url, data=q, headers=HEADERS).json()
        return response

    def get_total_documents(self):
        q = self.combined_query['main']
        total = self.plain_search(self.es_url, self.stringify_datasets(), q)['hits']['total']
        return int(total)

    @staticmethod
    def get_indices():
        url = '{0}/_cat/indices?format=json'.format(es_url)
        response = ES_Manager.requests.get(url, headers=HEADERS).json()
        indices = sorted([{'index': i['index'], 'status': i['status'], 'docs_count': i['docs.count'], 'store_size': i['store.size']} for i in response], key=lambda k: k['index'])

        # Filter according to prefix
        if es_prefix:
            indices = [i for i in indices if i['index'].startswith(es_prefix)]
        return indices

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
                self.combined_query['main']['query']['bool']['must'].append({'or': target_list})
            else:
                target_list = self.combined_query['main']['query']['bool']['must']
            for constraint in query_dict['main']['query']['bool']['should']:
                target_list.append(constraint)
        if 'must_not' in query_dict['main']['query']['bool'] and query_dict['main']['query']['bool']['must_not']:
            for constraint in query_dict['main']['query']['bool']['must_not']:
                self.combined_query['main']['query']['bool']['must_not'].append(constraint)

    def more_like_this_search(self, fields, stopwords=[], docs_accepted=[], docs_rejected=[], handle_negatives='ignore', search_size=10):

        # Get ids from basic search
        docs_search = self._scroll_doc_ids()
        # Combine ids from basic search and mlt search

        docs_search = [json.dumps(d) for d in docs_search]
        docs_accepted = [json.dumps(d) for d in docs_accepted]

        docs_combined = list(set().union(docs_search, docs_accepted))

        docs_combined = [json.loads(d) for d in docs_search]

        mlt = {
            "more_like_this": {
                "fields": fields,
                "like": docs_combined,
                "min_term_freq": 1,
                "max_query_terms": 12,
            }
        }

        if stopwords:
            mlt["more_like_this"]["stop_words"] = stopwords

        highlight_fields = {}
        for field in fields:
            highlight_fields[field] = {}

        query = {
            "query": {
                "bool": {
                    "must": [mlt]
                }
            },
            "size": search_size,
            "highlight": {
                "pre_tags": ["<b>"],
                "post_tags": ["</b>"],
                "fields": highlight_fields
            }
        }

        if docs_rejected:
            if handle_negatives == 'unlike':
                mlt["more_like_this"]["unlike"] = self._add_doc_ids_to_query(docs_rejected)
            elif handle_negatives == 'ignore':
                rejected = [{'ids': {'values': docs_rejected}}]
                query["query"]["bool"]["must_not"] = rejected

        response = ES_Manager.plain_search(self.es_url, self.stringify_datasets(), query)

        return response

    def _add_doc_ids_to_query(self, ids):
        return [{"_index": self.stringify_datasets(), "_id": id} for id in ids]

    def _scroll_doc_ids(self, limit=500):
        ids = []

        response = self.scroll(id_scroll=True, size=100)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        while hits:
            hits = response['hits']['hits']
            for hit in hits:
                ids.append({'_index': hit['_index'], '_type': hit['_type'], '_id': hit['_id']})
                if len(ids) == limit:
                    return ids
            response = self.scroll(scroll_id=scroll_id)
            scroll_id = response['_scroll_id']

        return ids

    def perform_queries(self, queries):
        response = ES_Manager.plain_multisearch(self.es_url, queries)
        return response

    def perform_query(self, query):
        response = ES_Manager.plain_search(self.es_url, self.stringify_datasets(), query)
        return response

    def get_extreme_dates(self, field):
        query = {"aggs": {"max_date": {"max": {"field": field}}, "min_date": {"min": {"field": field, 'format': 'yyyy-MM-dd'}}}}
        url = "{0}/{1}/_search".format(self.es_url, self.stringify_datasets())
        response = requests.post(url, data=json.dumps(query), headers=HEADERS).json()
        aggs = response["aggregations"]

        _min = self._timestamp_to_str(aggs["min_date"]["value"])
        _max = self._timestamp_to_str(aggs["max_date"]["value"])

        print(_min, _max)

        return _min, _max

    @staticmethod
    def _timestamp_to_str(timestamp):
        date_object = datetime.date.fromtimestamp(timestamp / 1000)
        return datetime.date.strftime(date_object, date_format)

    def clear_readonly_block(self):
        """changes read_only_allow_delete to False"""
        data = {"index": {"blocks": {"read_only_allow_delete": "false"}}}
        url = "{0}/{1}/_settings".format(self.es_url, self.stringify_datasets())
        response = self.plain_put(url, json.dumps(data))
        return response

    def get_mapping_schema(self) -> dict:
        """
        Using the _mapping endpoint of Elasticsearch, returns the mapping dictionary
        of all the indices specified. Supports multi-index.
        :return: Mappings of the doc_types.
        """
        endpoint_url = '{0}/{1}/_mapping'.format(es_url, self.stringify_datasets())
        response = self.plain_get(endpoint_url)
        return response

    def get_document_count(self, query: dict) -> int:
        """
        Returns how many documents are returned from a query using Elasticsearch's
        _count API.
        :param query: Dictionary of the search query send to Elasticsearch.
        :return: Integer of the amount of documents that correspond to the search query.
        """
        endpoint_url = '{0}/{1}/_count'.format(es_url, self.stringify_datasets())
        response = ES_Manager.requests.get(url=endpoint_url, json=query).json()
        return response['count']

    def get_field_mappings(self) -> dict:
        """
        Uses the _mapping endpoint to fetch the mapping data of ALL the fields in
        the specified indices. This includes Elasticsearch's built-in values like "_id" and "_source".
        :return:
        """
        url_endpoint = "{0}/{1}/_mapping/*/field/*".format(self.es_url, self.stringify_datasets())
        response = requests.get(url_endpoint).json()

        return response


    def add_is_nested_to_fields(self, nested_fields, fields_and_types: List[Dict], field_name_key='full_path'):
        """
        Given a list of dictionaries where the keys are field names,
        adds a value that determines if that field is of the nested datatype.
        :param nested_fields:
        :param field_name_key: Key name that contains the field name.
        :param fields_and_types: List of dictionaries that contain an ES field names (including dot notation)
        :return:
        """
        new_list = []

        for field_dict in fields_and_types:
            for nested_field_name in nested_fields:
                if nested_field_name in field_dict[field_name_key]:
                    field_dict['is_nested'] = True
                else:
                    field_dict['is_nested'] = False
                new_list.append(field_dict)

        return new_list

    def get_nested_field_names(self):
        """
        Traverses the doc_type's mapping schema to return
        a list with unique field names of fields that are of the nested datatype.
        Supports multiple indices.
        :return:
        """
        index_mapping = self.get_mapping_schema()
        nested_field_names = []

        for index_name, index_dict in index_mapping.items():
            for mapping_name, mapping_dict in index_dict['mappings'].items():
                for field_name, field_dict in mapping_dict['properties'].items():
                    if field_dict.get('type', None) == "nested":
                        nested_field_names.append(field_name)

        without_duplicates = list(set(nested_field_names))
        return without_duplicates

    def get_field_types(self, filtered_field_mapping) -> List[Dict[str, str]]:
        """
        Parses the results of the _mapping endpoint for fields to extract only the
        full path name of the field and its type. Nested fields are not included,
        multi-fields are by dot notation.
        :return:
        """
        all_fields = []

        for field_name, field_dict in filtered_field_mapping.items():
            if field_dict['mapping']:  # Empty dicts evaluate to False.
                full_path_and_types = dict()
                mapping_key = list(field_dict['mapping'].keys())[0]

                full_path_and_types['full_path'] = field_dict['full_name']
                full_path_and_types['type'] = field_dict['mapping'][mapping_key]['type']
                all_fields.append(full_path_and_types)

        return all_fields

    def get_filtered_field_mappings(self, es_field_mappings: dict)-> dict:
        """
        Given the results of the _mapping endpoint for fields,
        removes all keys that contains built-in ES values.
        :return:
        """
        elastic_keys = ["_seq_no", "_mapping", "_id", "_version", "_uid", "_type", "_source", "_field_names", "_all", "_index", "_parent", "_routing"]
        filtered_dict = dict()

        for index_name, index_dict in es_field_mappings.items():
            for mapping_name, mappings_dict in index_dict['mappings'].items():
                for field_name, field_dict in mappings_dict.items():
                    if field_name not in elastic_keys:
                        filtered_dict[field_name] = field_dict

        return filtered_dict

    def split_nested_fields(self, fields_and_types: List[Dict]):
        nested_fields = []
        normal_fields = []

        for field in fields_and_types:
            if field.get('is_nested', None) is True:
                nested_fields.append(field)
            elif field.get('is_nested', None) is False:
                normal_fields.append(field)

        return normal_fields, nested_fields

    def get_aggregation_field_data(self):
        """
        Implements the helper functions to give the necessary data
        about fields which is needed for the aggregations.
        :return:
        """
        names_of_nested_fields = self.get_nested_field_names()

        field_mappings = self.get_field_mappings()
        filtered_field_mappings = self.get_filtered_field_mappings(field_mappings)
        fieldnames_and_types = self.get_field_types(filtered_field_mappings)
        with_is_nested = self.add_is_nested_to_fields(names_of_nested_fields, fieldnames_and_types)

        normal_fields, nested_fields = self.split_nested_fields(with_is_nested)

        for nested_field in nested_fields:
            nested_field['parent'] = nested_field['full_path'].split('.')[0]  # By ES dot notation, "field.data"

        return normal_fields, nested_fields
