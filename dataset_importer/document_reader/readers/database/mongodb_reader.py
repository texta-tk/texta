

class MongoDBReader(object):

    @staticmethod
    def get_features(**kwargs):
        raise NotImplementedError()

    @staticmethod
    def count_total_documents(**kwargs):
        raise NotImplementedError()