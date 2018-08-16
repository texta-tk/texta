from .settings import storer_map


class DocumentStorer(object):
    """Storer factory for retrieving storer of the appropriate type. Storers are used to store read and preprocessed documents.
    """

    @staticmethod
    def get_storer(**connection_parameters):
        """Retrieves storer instance of the desired type.

        :param connection_parameters: must include storer
        :return: instance of a storer
        """
        return storer_map[connection_parameters['storer']]['class'](**connection_parameters)