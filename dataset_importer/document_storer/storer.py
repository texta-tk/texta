from .settings import storer_map


class DocumentStorer(object):

    @staticmethod
    def get_storer(**connection_parameters):
        return storer_map[connection_parameters['storer']](**connection_parameters)
    #
    # @staticmethod
    # def exists(**connection_parameters):
    #     return ElasticStorer.exists(**connection_parameters)
