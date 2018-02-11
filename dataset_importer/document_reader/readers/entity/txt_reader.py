from entity_adapter import EntityAdapter


class TXTAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in TXTAdapter.get_file_list(directory, 'txt'):
            features = TXTAdapter.get_meta_features(file_path=file_path)

            with open(file_path, 'rb') as text_file:
                features['text'] = text_file.read()

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return TXTAdapter.count_documents(directory_path=directory, extension='txt')