import textract
from entity_reader import EntityReader


class PDFReader(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        directory = kwargs['directory']

        for file_path in PDFReader.get_file_list(directory, 'pdf'):
            features = PDFReader.get_meta_features(file_path=file_path)

            try:
                features['text'] = textract.process(file_path)
                features['_texta_id'] = file_path

                yield features
            except:
                continue

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return PDFReader.count_documents(root_directory=directory, extension='pdf')