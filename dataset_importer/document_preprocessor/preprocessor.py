from .settings import preprocessor_map


class DocumentPreprocessor(object):
    #
    # def __init__(self, subprocessors=[]):
    #     self._subprocessors = subprocessors
    #
    # def process(self, documents, **kwargs):
    #     for subprocessor in self._subprocessors:
    #         documents = subprocessor.transform(documents, **kwargs)
    #
    #     return documents

    @staticmethod
    def process(documents, preprocessors, **kwargs):
        for preprocessor_code in preprocessors:
            preprocessor = preprocessor_map[preprocessor_code]
            documents = preprocessor.transform(documents, **kwargs)

        return documents