

class DocumentProcessor(object):

    def __init__(self, subprocessors=[]):
        self._subprocessors = subprocessors

    def process(self, documents):
        for document in documents:
            for subprocessor in self._subprocessors:
                document = subprocessor.transform(document)

            yield document