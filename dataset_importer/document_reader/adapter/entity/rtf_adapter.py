from entity_adapter import EntityAdapter
import textract


class RTFAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in RTFAdapter.get_file_list(directory, 'rtf'):
            features = RTFAdapter.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return RTFAdapter.count_documents(directory_path=directory, extension='rtf')
