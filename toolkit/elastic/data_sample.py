from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.query import Query
import json


class DataSample:
    """Re-usable object for handling positive and negative data samples for Taggers and TorchTaggers."""
    def __init__(self, model_object, show_progress=None, join_fields=False, text_processor=None, add_negative_sample=False):
        self.tagger_object = model_object
        self.show_progress = show_progress
        self.join_fields = join_fields
        self.text_processor = text_processor
        self.add_negative_sample = add_negative_sample

        self.class_names, self.queries = self._prepare_class_names_with_queries()

        self.ignore_ids = []

        # retrive feedback
        self.feedback = self._get_feedback()
        # TODO: COMBINE FEEDBACK TO DATA


        # retrieve data sample for each class
        self.data = self._get_samples_for_classes()


    @staticmethod
    def _join_fields(list_of_dicts):
        return [" ".join(a.values()) for a in list_of_dicts]


    @staticmethod
    def _create_queries(fact_name, tags):
        '''Creates queries for finding documents for each tag.'''
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            queries.append(query.query)
        return queries


    def _prepare_class_names_with_queries(self):
        fact_name = self.tagger_object.fact_name
        if fact_name:
            class_names = self._get_tags(fact_name)
            queries = self._create_queries(fact_name, class_names)
        else:
            # use description as class name for binary decisions
            class_names = ['true']
            # if fact name not present, use query provided
            queries = [json.loads(self.tagger_object.query)]
        return class_names, queries


    def _get_tags(self, fact_name, min_count=1000, max_count=None):
        '''Finds possible tags for training by aggregating active project's indices.'''
        active_indices = list(self.tagger_object.project.indices)
        es_a = ElasticAggregator(indices=active_indices)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values


    def _get_samples_for_classes(self):
        """Returns samples for each class as a dict."""
        samples = {}
        for i, class_name in enumerate(self.class_names):
            self.show_progress.update_step(f"scrolling sample for {class_name}")
            self.show_progress.update_view(0)
            samples[class_name] = self._get_class_sample(self.queries[i])
        # if only one class, add negatives automatically
        # add negatives as additional class if asked
        if len(self.class_names) < 2 or self.add_negative_sample:
            self.show_progress.update_step("scrolling negative sample")
            self.show_progress.update_view(0)
            samples['false'] = self._get_negatives()
        return samples


    def _get_class_sample(self, query):
        """Returns sample for given class"""
        # iterator for retrieving positive sample by query
        positive_sample_iterator = ElasticSearcher(
            query=query,
            indices=self.tagger_object.project.indices,
            field_data=json.loads(self.tagger_object.fields),
            output=ElasticSearcher.OUT_DOC_WITH_ID,
            callback_progress=self.show_progress,
            scroll_limit=int(self.tagger_object.maximum_sample_size),
            text_processor=self.text_processor
        )
        positive_sample = []
        # set positive ids to ignore while scrolling for negatives
        for doc in positive_sample_iterator:
            self.ignore_ids.append(doc["_id"])
            # remove id from doc
            del doc["_id"]
            positive_sample.append(doc)
        # document doct to value string if asked
        if self.join_fields:
            positive_sample = self._join_fields(positive_sample)
        return positive_sample


    def _get_feedback(self):
        """Returns feedback for each class/predicion."""
        return {a: self._get_feedback_for_class(a) for a in self.class_names}


    def _get_feedback_for_class(self, prediction_to_match):
        """Returns feedback sample for a given class/tag/prediction."""
        # create feedback object for positive sample
        feedback_sample = Feedback(
            self.tagger_object.project.pk,
            model_pk=self.tagger_object.pk,
            model_type=self.tagger_object.MODEL_TYPE,
            prediction_to_match=prediction_to_match,
            text_processor=self.text_processor,
            callback_progress=self.show_progress,
        )
        # iterator to list
        feedback_sample = list(feedback_sample)
        feedback_sample_without_ids = []
        # set positive ids to ignore while scrolling for negatives
        for doc in feedback_sample:
            self.ignore_ids.append(doc["_id"])
            # remove id from doc
            del doc["_id"]
            feedback_sample_without_ids.append(doc)
        return feedback_sample_without_ids


    def _get_negatives(self):
        self.show_progress.update_step("scrolling negative sample")
        self.show_progress.update_view(0)
        # iterator for retrieving negative examples
        negative_sample_iterator = ElasticSearcher(
            indices=self.tagger_object.project.indices,
            field_data=json.loads(self.tagger_object.fields),
            output=ElasticSearcher.OUT_DOC,
            callback_progress=self.show_progress,
            text_processor=self.text_processor,

            # THIS IS WRONG
            scroll_limit=len(self.ignore_ids)*int(self.tagger_object.negative_multiplier),
            ignore_ids=self.ignore_ids,

        )
        # iterator to list
        negative_sample = list(negative_sample_iterator)
        # document doct to value string if asked
        if self.join_fields:
            negative_sample = self._join_fields(negative_sample)
        return negative_sample
