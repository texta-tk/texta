import textract
from entity_adapter import EntityAdapter


class PDFAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in PDFAdapter.get_file_list(directory, 'pdf'):
            features = PDFAdapter.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return PDFAdapter.count_documents(directory_path=directory, extension='pdf')