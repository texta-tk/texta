from storers import ElasticStorer


class DocumentStorer(object):

    @staticmethod
    def get_storer(**connection_parameters):
        return ElasticStorer(**connection_parameters)

    @staticmethod
    def exists(**connection_parameters):
        return ElasticStorer.exists(**connection_parameters)

    @staticmethod
    def remove(**connection_parameters):
        return ElasticStorer.remove(**connection_parameters)