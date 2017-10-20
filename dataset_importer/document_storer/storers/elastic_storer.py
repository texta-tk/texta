import requests
import json


class ElasticStorer(object):

    def __init__(self, **connection_parameters):
        self._es_url = connection_parameters['elastic_url']
        self._es_index = connection_parameters['elastic_index']
        self._es_mapping = connection_parameters['elastic_mapping']

        self._request = requests.Session()

        if 'elastic_auth' in connection_parameters:
            self._request.auth = connection_parameters['elastic_auth']

        self._create_index_if_not_exists(self._es_url, self._es_index, self._es_mapping)

    def _create_index_if_not_exists(self, url, index, mapping):
        index_creation_query = {"mappings": {mapping: {}}}
        self._request.put("{url}/{index}".format(**{
            'url': url,
            'index': index,
        }), data=json.dumps(index_creation_query))

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

    @staticmethod
    def exists(**connection_parameters):
        return requests.head("{url}/{index}/{mapping}".format(**{
            'url': connection_parameters['elastic_url'],
            'index': connection_parameters['elastic_index'],
            'mapping': connection_parameters['elastic_mapping']
        })).ok
