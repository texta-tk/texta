import logging
from typing import Tuple

import elasticsearch
import requests
from django.db import transaction
from elasticsearch import Elasticsearch

from toolkit.elastic.exceptions import ElasticTimeoutException, ElasticTransportException
from toolkit.settings import ERROR_LOGGER, ES_CONNECTION_PARAMETERS, ES_PASSWORD, ES_PREFIX, ES_URL, ES_USERNAME
from toolkit.tools.logger import Logger


def elastic_connection(func):
    """
    Decorator for wrapping Elasticsearch functions that are used in views,
    to return a properly formatted error message during connection issues
    instead of the typical HTTP 500 one.
    """


    def func_wrapper(*args, **kwargs):

        try:
            return func(*args, **kwargs)

        except elasticsearch.exceptions.TransportError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticTransportException(f"Transport to Elasticsearch failed with error: {e.error}")

        except elasticsearch.exceptions.ConnectionTimeout as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise ElasticTimeoutException(f"Connection to Elasticsearch timed out!")


    return func_wrapper


class ElasticCore:
    """
        Class for holding most general settings and Elasticsearch object itself
    """


    def __init__(self):
        self.connection = self._check_connection()
        self.es = self._create_client_interface()
        self.es_prefix = ES_PREFIX
        self.TEXTA_RESERVED = ['texta_facts']


    def _create_client_interface(self):
        """
        Support using multiple hosts by splitting a coma-separated ES_URL.
        Having empty strings for auth is safe and does nothing if ES isn't configured for users.
        For safety's sake we remove all connection parameters with None (default if not configured in env),
        and then throw the existing ones with dictionary unpacking as per the Urllib3HttpConnection class.
        """
        if self.connection:
            list_of_hosts = ES_URL.split(",")
            existing_connection_parameters = dict((key, value) for key, value in ES_CONNECTION_PARAMETERS.items() if value is not None)
            client = Elasticsearch(list_of_hosts, http_auth=(ES_USERNAME, ES_PASSWORD), **existing_connection_parameters)
            return client
        else:
            Logger().error("Error connecting to Elasticsearch")
            return None


    def _check_connection(self):
        try:
            requests.get(ES_URL)
            return True
        except:
            return False


    @staticmethod
    def check_for_security_xpack() -> bool:
        """
        Checks whether the Elasticsearch Security X-Pack module is in use
        with its SSL and user authentication support.
        """
        try:
            ec = ElasticCore()
            info = ec.es.xpack.info(categories="features")
            available = info["features"]["security"]["available"]
            return available
        except elasticsearch.exceptions.RequestError as e:
            # When XPACK is not installed the xpack module will lose the info function,
            # which will then create an error, return False in that case.
            return False


    def create_index(self, index, body=None):
        return self.es.indices.create(index=index, body=body, ignore=400)


    @elastic_connection
    def delete_index(self, index):
        # returns either {'acknowledged': True} or a detailed error response
        return self.es.indices.delete(index=index, ignore=[400, 404])


    def get_mapping(self, index):
        return self.es.indices.get_mapping(index=index)


    @elastic_connection
    def close_index(self, index: str):
        return self.es.indices.close(index=index, ignore=[400, 404])


    @elastic_connection
    def open_index(self, index: str):
        return self.es.indices.open(index=index, ignore=[400, 404])


    @elastic_connection
    def syncher(self):
        """
        Wipe the slate clean and create a new set of Index objects.
        Since we're not using the destroy views, no actual deletion/creation operations
        will be done on the Elasticsearch cluster.

        Put this into a separate function to make using it
        """
        from toolkit.elastic.models import Index
        with transaction.atomic():
            opened, closed = self.get_indices()

            # Delete the overreaching parts.
            es_set = {index for index in opened + closed}
            tk_set = {index.name for index in Index.objects.all()}

            for index in tk_set:
                if index not in es_set:
                    Index.objects.get(name=index).delete()

            open_indices = [Index(name=index_name, is_open=True) for index_name in opened]
            closed_indices = [Index(name=index_name, is_open=False) for index_name in closed]

            for index in open_indices + closed_indices:
                Index.objects.get_or_create(name=index)


    @elastic_connection
    def get_indices(self) -> Tuple[list, list]:
        """
        Returns a tuple of open and closed list of indices that matches the ES_PREFIX,
        if it's not set, returns all indices in the server.
        """
        if self.connection:
            alias = '*'
            if self.es_prefix:
                alias = f'{self.es_prefix}*'
                opened = list(self.es.indices.get_alias(alias, expand_wildcards="open").keys())
                closed = list(self.es.indices.get_alias(alias, expand_wildcards="closed").keys())
                return opened, closed

            opened = list(self.es.indices.get_alias(alias, expand_wildcards="open").keys())
            closed = list(self.es.indices.get_alias(alias, expand_wildcards="closed").keys())
            return opened, closed
        else:
            return [], []


    def get_fields(self, indices=[]):
        out = []
        if indices:
            lookup = ','.join(indices)
        else:
            lookup = '*'
        if self.connection:
            for index, mappings in self.es.indices.get_mapping(lookup).items():
                for mapping, properties in mappings['mappings'].items():
                    properties = properties['properties']
                    for field in self._decode_mapping_structure(properties):
                        index_with_field = {'index': index, 'path': field['path'], 'type': field['type']}
                        out.append(index_with_field)
        return out


    def _decode_mapping_structure(self, structure, root_path=list(), nested_layers=list()):
        """
        Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []
        for k, v in structure.items():
            # deal with fact field
            if 'properties' in v and k in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = [{'path': k, 'type': 'fact'}]
                mapping_data.extend(sub_mapping)
            # deal with object & nested structures
            elif 'properties' in v and k not in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = self._decode_mapping_structure(sub_structure, root_path=path_list)
                mapping_data.extend(sub_mapping)
            else:
                path_list = root_path[:]
                path_list.append(k)
                path = '.'.join(path_list)
                data = {'path': path, 'type': v['type']}
                mapping_data.append(data)
        return mapping_data


    def check_if_indices_exist(self, indices):
        return self.es.indices.exists(index=','.join(indices))
