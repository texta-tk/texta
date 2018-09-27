from entity_reader import EntityReader

from dataset_importer.utils import HandleDatasetImportException


class HTMLAdapter(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        try:
            raise NotImplementedError()
        except Exception as e:
            HandleDatasetImportException(kwargs, e, file_path='')


    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return HTMLAdapter.count_documents(root_directory=directory, extension='html')
