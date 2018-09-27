from collection_reader import CollectionReader


class XMLReader(CollectionReader):

    @staticmethod
    def get_features(**kwargs):
        raise NotImplementedError()

    @staticmethod
    def count_total_documents(**kwargs):
        raise NotImplementedError()