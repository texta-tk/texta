

class DocumentProcessor(object):

    def __init__(self, subprocessors=[]):
        self._subprocessors = subprocessors

    def process(self, documents):
        for subprocessor in self._subprocessors:
            documents = subprocessor.transform(documents)

        return documents