from entity_reader import EntityReader
import textract


class RTFReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in RTFReader.get_file_list(directory, 'rtf'):
            features = RTFReader.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            features['_texta_id'] = file_path

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return RTFReader.count_documents(root_directory=directory, extension='rtf')
