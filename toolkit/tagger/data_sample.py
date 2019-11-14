from toolkit.elastic.searcher import ElasticSearcher
import json


class DataSample:
    """Re-usable object for handling positive and negative data samples for Taggers and TorchTaggers."""
    def __init__(self, model_object, show_progress=None, join_fields=False):
        self.tagger_object = model_object
        self.show_progress = show_progress
        self.join_fields = join_fields
        self.positive_ids = []
        self.positives = self._get_positives()
        self.negatives = self._get_negatives()

    @staticmethod
    def _join_fields(list_of_dicts):
        return [" ".join(a.values()) for a in list_of_dicts]

    def _get_positives(self):
        self.show_progress.update_step('scrolling positive sample')
        self.show_progress.update_view(0)
        # iterator for retrieving positive sample by query
        positive_sample_iterator = ElasticSearcher(
            query=json.loads(self.tagger_object.query),
            indices=self.tagger_object.project.indices,
            field_data=json.loads(self.tagger_object.fields),
            output=ElasticSearcher.OUT_DOC_WITH_ID,
            callback_progress=self.show_progress,
            scroll_limit=int(self.tagger_object.maximum_sample_size),
        )
        positive_sample = []
        # set positive ids to ignore while scrolling for negatives
        for doc in positive_sample_iterator:
            self.positive_ids.append(doc["_id"])
            # remove id from doc
            del doc["_id"]
            positive_sample.append(doc)
        
        # document doct to value string if asked
        if self.join_fields:
            positive_sample = self._join_fields(positive_sample)
        return positive_sample

    def _get_negatives(self):
        self.show_progress.update_step('scrolling negative sample')
        self.show_progress.update_view(0)
        # iterator for retrieving negative examples
        negative_sample_iterator = ElasticSearcher(
            indices=self.tagger_object.project.indices,
            field_data=json.loads(self.tagger_object.fields),
            output=ElasticSearcher.OUT_DOC,
            callback_progress=self.show_progress,
            scroll_limit=len(self.positive_ids)*int(self.tagger_object.negative_multiplier),
            ignore_ids=self.positive_ids,
        )
        # iterator to list
        negative_sample = list(negative_sample_iterator)
        # document doct to value string if asked
        if self.join_fields:
            negative_sample = self._join_fields(negative_sample)
        return negative_sample
