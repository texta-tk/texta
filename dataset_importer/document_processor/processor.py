

class DocumentProcessor(object):

    def __init__(self, subprocessors=[]):
        self._subprocessors = subprocessors

    def process(self, documents, **kwargs):
        for subprocessor in self._subprocessors:
            documents = subprocessor.transform(documents, **kwargs)

        return documents