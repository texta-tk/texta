from entity_adapter import EntityAdapter
import textract


class DocAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in DocAdapter.get_file_list(directory, 'doc'):
            features = DocAdapter.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return DocAdapter.count_documents(directory_path=directory, extension='doc')
