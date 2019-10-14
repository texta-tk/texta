import requests
from elasticsearch import Elasticsearch

from toolkit.settings import ES_CONNECTION_PARAMETERS, ES_PASSWORD, ES_PREFIX, ES_URL, ES_USERNAME


class ElasticCore:
    """
    Class for holding most general settings and Elasticsearch object itself
    """

    def __init__(self):
        self.es = self._create_client_interface()
        self.es_prefix = ES_PREFIX
        self.connection = self._check_connection()
        self.TEXTA_RESERVED = ['texta_facts']

    def _create_client_interface(self):
        """
        Support using multiple hosts by splitting a coma-separated ES_URL.
        Having empty strings for auth is safe and does nothing if ES isn't configured for users.
        For safety's sake we remove all connection parameters with None (default if not configured in env),
        and then throw the existing ones with dictionary unpacking as per the Urllib3HttpConnection class.
        """
        list_of_hosts = ES_URL.split(",")
        existing_connection_parameters = dict((key, value) for key, value in ES_CONNECTION_PARAMETERS.items() if value is not None)
        client = Elasticsearch(list_of_hosts, http_auth=(ES_USERNAME, ES_PASSWORD), **existing_connection_parameters)
        return client

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
        ec = ElasticCore()
        info = ec.es.xpack.info(categories="features")
        available = info["features"]["security"]["available"]
        return available

    def create_index(self, index, body):
        return self.es.indices.create(index=index, ignore=400, body=body)

    # use with caution
    def delete_index(self, index):
        # returns either {'acknowledged': True} or a detailed error response
        return self.es.indices.delete(index=index, ignore=[400, 404])

    def get_mapping(self, index):
        return self.es.indices.get_mapping(index=index)

    def get_indices(self):
        if self.connection:
            alias = '*'
            if self.es_prefix:
                alias = f'{self.es_prefix}_*'
                return list(self.es.indices.get_alias(alias).keys())

            return list(self.es.indices.get_alias().keys())
        else:
            return []

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
