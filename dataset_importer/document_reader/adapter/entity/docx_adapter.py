from entity_adapter import EntityAdapter
import textract


class DocXAdapter(EntityAdapter):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in DocXAdapter.get_file_list(directory, 'docx'):
            features = DocXAdapter.get_meta_features(file_path=file_path)

            features['text'] = textract.process(file_path)

            yield features

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return DocXAdapter.count_documents(directory_path=directory, extension='docx')
