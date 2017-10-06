import textract
from entity_adapter import EntityAdapter


class PDFAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['file_path']

        for file_path in PDFAdapter.get_file_list(directory, 'txt'):
            features = PDFAdapter.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            yield features
