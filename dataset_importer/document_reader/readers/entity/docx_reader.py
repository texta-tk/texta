from entity_reader import EntityReader
import textract

from dataset_importer.utils import HandleDatasetImportException


class DocXReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):

        directory = kwargs['directory']

        for file_path in DocXReader.get_file_list(directory, 'docx'):
            try:
                features = DocXReader.get_meta_features(file_path=file_path)
                features['text'] = textract.process(file_path)
                features['_texta_id'] = file_path

                yield features

            except Exception as e:
                HandleDatasetImportException(kwargs, e, file_path=file_path)

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return DocXReader.count_documents(root_directory=directory, extension='docx')
