from entity_reader import EntityReader
import textract


class DocReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in DocReader.get_file_list(directory, 'doc'):
            features = DocReader.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return DocReader.count_documents(root_directory=directory, extension='doc')
