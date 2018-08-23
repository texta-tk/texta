from .settings import preprocessor_map

PREPROCESSOR_INSTANCES = {
    preprocessor_code: preprocessor['class'](**preprocessor['arguments'])
    for preprocessor_code, preprocessor in preprocessor_map.items() if preprocessor['is_enabled']
}


class DocumentPreprocessor(object):
    """A static document preprocessor adapter that dispatches the preprocessing request to appropriate preprocessor implementations.
    """

    @staticmethod
    def convert_to_utf8(document: dict) -> dict:
        """
        Loops through all key, value pairs in dict, checks if it is a string/bytes
        and tries to decode it to utf8.
        :param document: Singular document.
        :return: Singular document decoded into utf8.
        """
        for key, value in document.items():
            if type(value) is bytes:
                document[key] = value.decode('utf8')

        return document

    @staticmethod
    def process(documents, **kwargs):
        """Dispatches the preprocessing request for the provided documents to the provided preprocessors.

        SIDE EFFECT: alters the documents in place.

        :param documents: collection of key-value documents, which are to be preprocessed
        :param kwargs[preprocessors]: document enhancing entities, which add new features to the existing documents
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :type kwargs[preprocessors]: list of preprocessor implementation instances.
        :return: enhanced documents
        :rtype: list of dicts
        """
        preprocessors = kwargs['preprocessors']

        for preprocessor_code in preprocessors:
            preprocessor = PREPROCESSOR_INSTANCES[preprocessor_code]

            documents = list(map(DocumentPreprocessor.convert_to_utf8, documents))
            documents = preprocessor.transform(documents, **kwargs)
        return documents
