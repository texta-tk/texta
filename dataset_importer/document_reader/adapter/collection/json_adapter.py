from collection_adapter import CollectionAdapter
import json


class JSONAdapter(CollectionAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in JSONAdapter.get_file_list(directory, 'json'):
            with open(file_path) as json_file:
                for line in json_file:
                    yield json.loads(line.strip())

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']

        total_documents = 0

        for file_path in JSONAdapter.get_file_list(directory, 'json'):
            with open(file_path) as json_file:
                total_documents += sum(1 for row in json_file)

        return total_documents