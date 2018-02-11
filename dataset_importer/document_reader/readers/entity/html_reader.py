

class HTMLAdapter(object):

    @staticmethod
    def get_features(file_obj):
        raise NotImplementedError()

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        return HTMLAdapter.count_documents(directory_path=directory, extension='html')
