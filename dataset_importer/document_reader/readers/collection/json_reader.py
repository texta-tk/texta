from collection_reader import CollectionReader
import json
import itertools


class JSONReader(CollectionReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in JSONReader.get_file_list(directory, 'json'):
            with open(file_path) as json_file:
                content = json_file.readlines()
                try:
                    for line_idx, line in enumerate(content):
                        features = json.loads(line.strip())
                        features['_texta_id'] = '{0}_{1}'.format(file_path, line_idx)
                        yield features
                except:
                    new_content = ''
                    idx_list = []
                    for line_idx, line in enumerate(content):
                        if line[0] not in ['\t', '\n', ' ']:
                            idx_list.append(line_idx)

                    idx_list = [(idx_list[i], idx_list[i+1]) for i in range(0, len(idx_list), 2)]

                    for pair in idx_list:
                        new_content += ''.join(content[pair[0]:pair[1] + 1]).replace('\n', '').replace('\t', ' ') + '\n'

                    with open(directory + '/tmp.json', 'w', encoding='utf8') as f:
                        f.write(new_content)

                    with open(directory + '/tmp.json', 'r', encoding='utf8') as f:
                        for line_idx, line in enumerate(f):
                            features = json.loads(line.strip())
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