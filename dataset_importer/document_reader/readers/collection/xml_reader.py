from collection_reader import CollectionReader


class XMLReader(CollectionReader):

    @staticmethod
    def get_features(file_obj):
        raise NotImplementedError()