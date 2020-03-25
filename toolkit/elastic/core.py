import logging
from typing import List, Tuple

import elasticsearch
import requests
from django.db import transaction
from elasticsearch import Elasticsearch

from toolkit.elastic.exceptions import ElasticAuthenticationException, ElasticAuthorizationException, ElasticIndexNotFoundException, ElasticTimeoutException, ElasticTransportException
from toolkit.settings import ERROR_LOGGER, ES_CONNECTION_PARAMETERS
from toolkit.helper_functions import get_core_setting
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

        except elasticsearch.exceptions.NotFoundError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            info = [error["index"] for error in e.info["error"]["root_cause"]]
            raise ElasticIndexNotFoundException(f"Index lookup failed: {str(info)}")

        except elasticsearch.exceptions.AuthorizationException as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            error = [error["reason"] for error in e.info["error"]["root_cause"]]
            raise ElasticAuthorizationException(f"Not authorized to access resource: {str(error)}")

        except elasticsearch.exceptions.AuthenticationException as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticAuthenticationException(f"Not authorized to access resource: {e.info}")

        except elasticsearch.exceptions.TransportError as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticTransportException(f"Transport to Elasticsearch failed with error: {e.error}")

        except elasticsearch.exceptions.ConnectionTimeout as e:
            logging.getLogger(ERROR_LOGGER).exception(e.info)
            raise ElasticTimeoutException(f"Connection to Elasticsearch timed out!")


    return func_wrapper


class ElasticCore:
    """
        Class for holding most general settings and Elasticsearch object itself
    """


    def __init__(self, ES_URL=get_core_setting("TEXTA_ES_URL")):
        self.ES_URL = ES_URL
        self.ES_PREFIX = get_core_setting("TEXTA_ES_PREFIX")
        self.ES_USERNAME = get_core_setting("TEXTA_ES_USERNAME")
        self.ES_PASSWORD = get_core_setting("TEXTA_ES_PASSWORD")
        self.TEXTA_RESERVED = ['texta_facts']

        self.connection = self._check_connection()
        self.es = self._create_client_interface()


    def _create_client_interface(self):
        """
        Support using multiple hosts by splitting a coma-separated ES_URL.
        Having empty strings for auth is safe and does nothing if ES isn't configured for users.
        For safety's sake we remove all connection parameters with None (default if not configured in env),
        and then throw the existing ones with dictionary unpacking as per the Urllib3HttpConnection class.
        """
        if self.connection:
            list_of_hosts = self.ES_URL.split(",")
            existing_connection_parameters = dict((key, value) for key, value in ES_CONNECTION_PARAMETERS.items() if value is not None)
            client = Elasticsearch(list_of_hosts, http_auth=(self.ES_USERNAME, self.ES_PASSWORD), **existing_connection_parameters)
            return client
        else:
            return None


    def _check_connection(self):
        try:
            response = requests.get(self.ES_URL)
            if response.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
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


    @elastic_connection
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

            # Create an Index object if it doesn't exist in the right open/closed state.
            # Ensures that changes Elastic-side on the open/closed state are forcefully updated.
            for index in opened:
                index, is_created = Index.objects.get_or_create(name=index)
                index.is_open = True
                index.save()

            for index in closed:
                index, is_created = Index.objects.get_or_create(name=index)
                index.is_open = False
                index.save()


    @elastic_connection
    def get_indices(self) -> Tuple[list, list]:
        """
        Returns a tuple of open and closed list of indices that matches the ES_PREFIX,
        if it's not set, returns all indices in the server.
        """
        if self.connection:
            alias = '*'
            if self.ES_PREFIX:
                alias = f'{self.ES_PREFIX}*'
                opened = list(self.es.indices.get_alias(alias, expand_wildcards="open").keys())
                closed = list(self.es.indices.get_alias(alias, expand_wildcards="closed").keys())
                return opened, closed

            opened = list(self.es.indices.get_alias(alias, expand_wildcards="open").keys())
            closed = list(self.es.indices.get_alias(alias, expand_wildcards="closed").keys())
            return opened, closed
        else:
            return [], []


    @elastic_connection
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


    @elastic_connection
    def check_if_indices_exist(self, indices: List[str]) -> bool:
        """
        Returns whether the given indices exist using a list of index
        names as input.
        """
        return self.es.indices.exists(index=','.join(indices))


    @elastic_connection
    def scroll(self, indices: List[str], query: dict, scroll_id: str = None, connection_timeout=60 * 1, scroll_timeout="10m", size=300, fields: List[str] = ["*"], with_meta=True):
        indices = ",".join(indices)
        if scroll_id is None:
            initial_scroll = self.es.search(index=indices, body=query, request_timeout=connection_timeout, scroll=scroll_timeout, size=size, _source=fields)
            documents = initial_scroll["hits"]["hits"] if with_meta else [doc["_source"] for doc in initial_scroll["hits"]["hits"]]
            response = {
                "scroll_id": initial_scroll["_scroll_id"],
                "total_documents": initial_scroll["hits"]["total"],
                "returned_count": len(initial_scroll["hits"]["hits"]),
                "documents": documents
            }
            return response

        else:
            continuation_scroll = self.es.scroll(scroll_id=scroll_id, scroll=scroll_timeout)
            documents = continuation_scroll["hits"]["hits"] if with_meta else [doc["_source"] for doc in continuation_scroll["hits"]["hits"]]

            response = {
                "scroll_id": continuation_scroll["_scroll_id"],
                "total_documents": continuation_scroll["hits"]["total"],
                "returned_count": len(continuation_scroll["hits"]["hits"]),
                "documents": documents
            }
            return response
