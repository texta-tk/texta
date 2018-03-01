from entity_reader import EntityReader
import textract


class DocXReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in DocXReader.get_file_list(directory, 'docx'):
            features = DocXReader.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return DocXReader.count_documents(root_directory=directory, extension='docx')
