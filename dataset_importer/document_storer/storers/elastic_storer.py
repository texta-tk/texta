import requests
import json


class ElasticStorer(object):

    def __init__(self, **connection_parameters):
        self._es_url = connection_parameters['texta_elastic_url']
        self._es_index = connection_parameters['texta_elastic_index']
        self._es_mapping = connection_parameters['texta_elastic_mapping']

        self._request = requests.Session()

        if 'elastic_auth' in connection_parameters:
            self._request.auth = connection_parameters['elastic_auth']

        self._create_index_if_not_exists(self._es_url, self._es_index, self._es_mapping,
                                         json.loads(connection_parameters['texta_elastic_not_analyzed']))

    def _create_index_if_not_exists(self, url, index, mapping, not_analyzed_fields):
        index_creation_query = {"mappings": {mapping: {'properties': {'texta_facts': {'type': 'nested'}}}}}
        self._add_not_analyzed_declarations(index_creation_query['mappings'][mapping], not_analyzed_fields)
        print(index_creation_query)
        self._request.put("{url}/{index}".format(**{
            'url': url,
            'index': index,
        }), data=json.dumps(index_creation_query))

    def _add_not_analyzed_declarations(self, mapping_dict, not_analyzed_fields):
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

            current_dict['type'] = 'string'
            current_dict['index'] = 'not_analyzed'

    def store(self, documents):
        if not documents:
            return

        if not isinstance(documents, list):
            documents = list(documents)

        data_to_send = []

        if 'elastic_id' in documents[0]:  # Use predefined ID value
            for document in documents:
                meta_data = {
                    'index': {'_index': self._es_index, '_type': self._es_mapping, '_id': document['elastic_id']}
                }
                del document['elastic_id']
                data_to_send.append(json.dumps(meta_data))
                data_to_send.append(json.dumps(document))

            data_to_send.append('\n')
            self._request.put("%s/%s/%s/_bulk" % (self._es_url, self._es_index, self._es_mapping),
                              data='\n'.join(data_to_send))
        else:  # Let Elasticsearch generate random ID value
            for document in documents:
                meta_data = {'index': {'_index': self._es_index, '_type': self._es_mapping}}
                data_to_send.append(json.dumps(meta_data))
                data_to_send.append(json.dumps(document))

            data_to_send.append('\n')
            self._request.put("%s/%s/%s/_bulk" % (self._es_url, self._es_index, self._es_mapping),
                              data='\n'.join(data_to_send))

        return len(documents)

    # @staticmethod
    # def exists(**connection_parameters):
    #     return requests.head("{url}/{index}/{mapping}".format(**{
    #         'url': connection_parameters['elastic_url'],
    #         'index': connection_parameters['elastic_index'],
    #         'mapping': connection_parameters['elastic_mapping']
    #     })).ok

    def remove(self):
        self._request.delete("{url}/{index}".format(**{
            'url': self._es_url,
            'index': self._es_index
        }))
