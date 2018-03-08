from entity_reader import EntityReader


class HTMLAdapter(EntityReader):

    @staticmethod
    def get_features(**kwargs):
        raise NotImplementedError()

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return HTMLAdapter.count_documents(root_directory=directory, extension='html')
