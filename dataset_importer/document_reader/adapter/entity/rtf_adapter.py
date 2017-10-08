from entity_adapter import EntityAdapter
import textract


class RTFAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['file_path']

        for file_path in RTFAdapter.get_file_list(directory, 'txt'):
            features = RTFAdapter.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            yield features