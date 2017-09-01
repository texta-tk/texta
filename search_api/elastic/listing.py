import requests


class ElasticListing(object):

    def __init__(self, es_url):
        self._es_url = es_url.strip('/')

    def get_existing_datasets(self, datasets):
        try:
            requests.get(self._es_url)
        except:
            return []

        existing_datasets = []

        for dataset in datasets:
            try:
                response = requests.get('{0}/{1}/_mappings/{2}'.format(self._es_url, dataset.index, dataset.mapping)).json()
                if dataset.mapping in response[dataset.index]['mappings']:
                    existing_datasets.append({'id': dataset.id,
                                              'index': dataset.index,
                                              'mappping': dataset.mapping,
                                              'author': dataset.author.username})
            except:
                continue
        return existing_datasets

    def get_dataset_properties(self, dataset):
        try:
            response = requests.get('{0}/{1}/_mappings/{2}'.format(self._es_url, dataset.index, dataset.mapping)).json()
            return response[dataset.index]['mappings'][dataset.mapping]
        except:
            return {}