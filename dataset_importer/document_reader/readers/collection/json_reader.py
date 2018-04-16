from collection_reader import CollectionReader
import json

class JSONReader(CollectionReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in JSONReader.get_file_list(directory, 'json'):
            with open(file_path) as json_file:
                content = json_file.readlines()
                    for line_idx, line in enumerate(content):
                        features = json.loads([x for x in line.strip() if len(x) > 0])
                        features['_texta_id'] = '{0}_{1}'.format(file_path, line_idx)
                        yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']

        total_documents = 0

        for file_path in JSONReader.get_file_list(directory, 'json'):
            with open(file_path) as json_file:
                total_documents += sum(1 for row in json_file)

        return total_documents