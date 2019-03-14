from texta.settings import FACT_PROPERTIES, es_prefix
import requests
import elasticsearch
from elasticsearch.helpers import bulk
import json


class ElasticStorer(object):
    """Storer implementation for storing documents to Elasticsearch.
    """

    def __init__(self, **connection_parameters):
        self._es_url = connection_parameters['texta_elastic_url']
        self._es_index = self._correct_name(connection_parameters['texta_elastic_index'])
        self._es_mapping = self._correct_name(connection_parameters['texta_elastic_mapping'])
        self._es_analyzer = connection_parameters.get("elastic_analyzer")

        self._headers = {'Content-Type': 'application/json; charset=utf-8'}
        self._request = requests.Session()

        if 'elastic_auth' in connection_parameters:
            self._request.auth = connection_parameters['elastic_auth']
        self._create_index_if_not_exists(self._es_url, self._es_index, self._es_mapping,
                                         connection_parameters['texta_elastic_not_analyzed'].split('\n'))
        # json.loads(connection_parameters['texta_elastic_not_analyzed']))

    def _correct_name(self, name):
        name = name.lower().replace(' ', '_')
        # add prefix if necessary
        if es_prefix:
            name = es_prefix + name
        return name

    def _create_index_if_not_exists(self, url, index, mapping, not_analyzed_fields):
        """Prepares and creates an Elasticsearch index, if it is not existing yet.

        :param url: Elasticsearch instance's URL.
        :param index: name of the index.
        :param mapping: name of the mapping.
        :param not_analyzed_fields: Elasticsearch <=2.4 keywords equivalent.
        :type url: string
        :type index: string
        :type mapping: string
        :type not_analyzed_fields: list of strings
        """

        index_creation_query = {
            "mappings": {
                mapping: {
                    "properties": {
                        "texta_facts": FACT_PROPERTIES
                    },
                    "dynamic_templates": [
                        {"estonian": {
                            "match_mapping_type": "string",
                            "mapping": {
                                "type": "text",
                                "analyzer": self._es_analyzer
                            }
                        }
                        }
                    ]
                }
            }
        }

        # self._add_not_analyzed_declarations(index_creation_query['mappings'][mapping], not_analyzed_fields)
        self._request.put("{url}/{index}".format(**{
            'url': url,
            'index': index,
        }), data=json.dumps(index_creation_query), headers=self._headers)

    def _add_not_analyzed_declarations(self, mapping_dict, not_analyzed_fields):
        """Adds not analyzed fields to index creation schema.

        :param mapping_dict: schema of the relevant mapping as expected by Elasticsearch index creation.
        :param not_analyzed_fields: names of the fields which must not be analyzed.
        :type mapping_dict: dict
        :type not_analyzed_fields: list of strings
        """
        for not_analyzed_field in not_analyzed_fields:
            field_path = not_analyzed_field.split('.')
            current_dict = mapping_dict

            for path_element in field_path:
                if 'properties' not in current_dict:
                    current_dict['properties'] = {}
                current_dict = current_dict['properties']

                if path_element not in current_dict:
                    current_dict[path_element] = {}
                current_dict = current_dict[path_element]

            current_dict['type'] = 'keyword'
            # current_dict['index'] = 'not_analyzed'

    def store(self, documents):
        """Stores the provided documents to Elasticsearch'es appropriate index.

        :param documents: documents waiting to be stored.
        :type documents: list of dicts
        :return: number of documents stored
        :rtype: int
        """
        if not documents:
            return

        if not isinstance(documents, list):
            documents = list(documents)

        if 'elastic_id' in documents[0]:  # Use predefined ID value
            batch_payload = []

            for document in documents:
                meta_data = {'_index': self._es_index, '_type': self._es_mapping, '_id': document['elastic_id']}
                single_payload = {**meta_data, **document}
                batch_payload.append(single_payload)

            client = elasticsearch.Elasticsearch(hosts=[self._es_url])
            response = bulk(client=client, actions=batch_payload, stats_only=True, raise_on_error=False)

        else:  # Let Elasticsearch generate random ID value
            batch_payload = []

            for document in documents:
                meta_data = {'_index': self._es_index, '_type': self._es_mapping}
                single_payload = {**meta_data, **document}
                batch_payload.append(single_payload)

            client = elasticsearch.Elasticsearch(hosts=[self._es_url])
            response = bulk(client=client, actions=batch_payload)

        return len(documents)

    def remove(self):
        """Removes the Elasticsearch index.
        """
        self._request.delete("{url}/{index}".format(**{
            'url': self._es_url,
            'index': self._es_index
        }), headers=self._headers)
