import textract
from entity_reader import EntityReader
from dataset_importer.utils import HandleDatasetImportException

class PDFReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in PDFReader.get_file_list(directory, 'pdf'):
            features = PDFReader.get_meta_features(file_path=file_path)

            try:
                features['text'] = textract.process(file_path).decode('utf8')
                features['_texta_id'] = file_path

                yield features
            except Exception as e:
                HandleDatasetImportException(kwargs, e, file_path)

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return PDFReader.count_documents(root_directory=directory, extension='pdf')