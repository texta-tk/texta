import textract
from entity_reader import EntityReader


class PDFReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in PDFReader.get_file_list(directory, 'pdf'):
            features = PDFReader.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return PDFReader.count_documents(directory_path=directory, extension='pdf')