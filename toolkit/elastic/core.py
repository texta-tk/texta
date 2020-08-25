import collections
from typing import List, Tuple

import elasticsearch
import elasticsearch_dsl
import requests
from django.db import transaction
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Keyword, Long, Mapping, Nested
from rest_framework.exceptions import ValidationError

from toolkit.elastic.decorators import elastic_connection
from toolkit.helper_functions import get_core_setting
from toolkit.settings import ES_CONNECTION_PARAMETERS


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


    def _check_connection(self):
        try:
            response = requests.get(self.ES_URL)
            if response.status_code == 200:
                return True
            else:
                return False
        except Exception as e:
            raise ValidationError(f"Error connecting to Elasticsearch: '{self.ES_URL}'! Do you have the right URL configured?")


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
        return self.es.indices.create(index=index, body=body, ignore=[400, 404])


    @elastic_connection
    def delete_index(self, index):
        # returns either {'acknowledged': True} or a detailed error response
        return self.es.indices.delete(index=index, ignore=[400, 404])


    @elastic_connection
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

            # Delete the parts that exist in the toolkit but not in Elasticsearch.
            es_set = {index for index in opened + closed}
            tk_set = {index.name for index in Index.objects.all()}
            for index in tk_set:
                if index not in es_set:
                    Index.objects.get(name=index).delete()

            # Create an Index object if it doesn't exist.
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


    @elastic_connection
    def add_texta_facts_mapping(self, index: str, doc_type=None):
        """
        To allow for more flexibility, we do not use the indices variable in the class.

        Adding the same mapping multiple times doesn't effect anything,
        adding a single field is also save as the query only adds, not overwrites.
        """
        m = Mapping(index) if doc_type is None else Mapping(doc_type)
        texta_facts = Nested(
            properties={
                "spans": Keyword(),
                "fact": Keyword(),
                "str_val": Keyword(),
                "doc_path": Keyword(),
                "num_val": Long(),
            }
        )

        # Set the name of the field along with its mapping body
        m.field("texta_facts", texta_facts)
        m.save(index=index, using=self.es)


    def flatten(self, d, parent_key='', sep='.'):
        """
        From: https://stackoverflow.com/questions/6027558/flatten-nested-dictionaries-compressing-keys
        """
        items = []
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, collections.MutableMapping):
                items.extend(self.flatten(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


    @elastic_connection
    def get_index_stats(self):
        store = {}
        indices = "_all"

        # Get size of indices.
        response = self.es.indices.stats(index=indices, metric="store")
        for index_name in response["indices"].keys():
            size = response["indices"][index_name]["total"]["store"]["size_in_bytes"]
            store[index_name] = {"size": size, "doc_count": 0}  # Initialize doc_count as zero and overwrite later.

        # Get count of indices.
        s = elasticsearch_dsl.Search(using=self.es, index=indices).extra(size=0)
        s.aggs.bucket("by_all", "terms", field="_index", size=10000)
        for hit in s.execute().aggs.by_all:
            index_name = hit["key"]
            store[index_name]["doc_count"] = hit["doc_count"]

        return store
