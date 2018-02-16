from classification_manager.model_pipeline import classify_documents


class ClassificationProcessor(object):
    def __init__(self, classifier_ids, feature_map={}):
        self._classifier_ids = classifier_ids
        self._feature_map = feature_map

    def transform(self, documents):
        if not self._classifier_ids:
            return documents

        if self._feature_map:
            feature_map = [key1_key2 for key1_key2 in self._feature_map.items()]
            # for document

        return classify_documents(self._classifier_ids, documents)
