import json
from typing import List, Optional

from texta_tools.text_processor import TextProcessor

from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.feedback import Feedback
from toolkit.elastic.tools.query import Query
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.tools.lemmatizer import ElasticLemmatizer
from .core import ElasticCore
from ..exceptions import InvalidDataSampleError
from ...tools.show_progress import ShowProgress


ES6_SNOWBALL_MAPPING = {
    "ca": "catalan",
    "da": "danish",
    "nl": "dutch",
    "en": "english",
    "fi": "finnish",
    "fr": "french",
    "de": "german",
    "hu": "hungarian",
    "it": "italian",
    "lt": "lithuanian",
    "no": "norwegian",
    "pt": "portuguese",
    "ro": "romanian",
    "ru": "russian",
    "es": "spanish",
    "sv": "swedish",
    "tr": "turkish",
}

ES7_SNOWBALL_MAPPING = {"ar": "arabic", "et": "estonian"}


class InvalidDataSampleError(Exception):
    """Raised on invalid Data Sample"""
    pass


class DataSample:
    """Re-usable object for handling positive and negative data samples for Taggers and TorchTaggers."""


    def __init__(self,
                 model_object,
                 indices: List[str],
                 field_data: List[str],
                 show_progress: ShowProgress = None,
                 join_fields=False,
                 text_processor: TextProcessor = None,
                 add_negative_sample=False,
                 snowball_language: str = None,
                 detect_lang: bool = False):
        """
        :param model_object:
        :param indices: List of Elasticsearch index names where the documents will be pulled from.
        :param field_data: List of field names from the JSON document to process.
        :param show_progress: Callback object used to store the progress inside the database.
        :param join_fields:
        :param text_processor:
        :param add_negative_sample:
        :param snowball_language: Which language stemmer to use on the document. Based on internal Elasticsearch values.
        :param detect_lang: Whether to apply the stemmer based on the pre-detected values in the document itself.
        """
        self.tagger_object = model_object
        self.show_progress = show_progress
        self.indices = indices
        self.field_data = field_data
        self.fields_with_language = [f"{field}_mlp.language.detected" for field in field_data] + field_data
        self.join_fields = join_fields
        self.text_processor = text_processor
        self.add_negative_sample = add_negative_sample
        self.detect_lang = detect_lang
        self.class_names, self.queries = self._prepare_class_names_with_queries()
        self.ignore_ids = set()

        # retrive feedback
        self.feedback = self._get_feedback()
        # retrieve data sample for each class
        self.data = self._get_samples_for_classes()
        # combine feedback & data dicts
        self.data = {**self.feedback, **self.data}

        # use Snowball stemmer
        if detect_lang is False:
            self._snowball(snowball_language)
        else:
            self._snowball_from_doc()

        # validate resulting data sample
        self._validate()

        self.is_binary = True if len(self.data) == 2 else False


    @staticmethod
    def humanize_lang_code(lang_code: str, base_mapping: dict = ES6_SNOWBALL_MAPPING, es7_mapping=ES7_SNOWBALL_MAPPING) -> Optional[str]:
        """
        https://www.elastic.co/guide/en/elasticsearch/reference/7.10/analysis-snowball-tokenfilter.html

        :param lang_code: Language string in ISO 639-1 format.
        :param base_mapping: Dictionary where the keys are ISO 639-1 codes and the values their humanised forms as per Elasticsearch 6 support.
        :param es7_mapping: Same as base_mapping but only includes new additions from Elasticsearch 7.
        :return: Humanized form of the language code that is compatible with the built-in Snowball options that Elasticsearch supports or None if it doesn't.
        """
        ec = ElasticCore()
        first, second, third = ec.get_version()
        if first == 6:
            humanized = base_mapping.get(lang_code, None)
            return humanized
        elif first == 7:
            full_mapping = {**base_mapping, **es7_mapping}
            humanized = full_mapping.get(lang_code, None)
            return humanized


    def _snowball(self, snowball_language):
        """
        Stems the texts in data sample using Snowball.
        """
        if snowball_language:
            lemmatizer = ElasticLemmatizer()
            for cl, examples in self.data.items():
                processed_examples = []
                for example_doc in examples:
                    new_example_doc = {k: lemmatizer.lemmatize(v, language=snowball_language) for k, v in example_doc.items()}
                    processed_examples.append(new_example_doc)
                self.data[cl] = processed_examples


    def _snowball_from_doc(self):
        """
        Stems the texts in data sample using Snowball.
        """
        lemmatizer = ElasticLemmatizer()
        for cl, examples in self.data.items():
            processed_examples = []
            for example_doc in examples:
                for key, value in example_doc.items():
                    # Use this string to differentiate between original and MLP added fields.
                    if "_mlp." not in key:
                        lang = example_doc.get(f"{key}_mlp.language.detected", None)
                        if lang is not None:
                            snowball_language = self.humanize_lang_code(lang)
                            if snowball_language:
                                example_doc[key] = lemmatizer.lemmatize(example_doc[key], snowball_language)
                processed_examples.append(example_doc)

            self.data[cl] = processed_examples


    @staticmethod
    def _join_fields(list_of_dicts):
        return [" ".join(a.values()) for a in list_of_dicts]


    @staticmethod
    def _create_queries(fact_name, tags, sub_query):
        """Creates queries for finding documents for each tag."""
        queries = []
        for tag in tags:
            query = Query()
            query.add_fact_filter(fact_name, tag)
            query.add_sub_query(sub_query)
            queries.append(query.query)
        return queries


    def _prepare_class_names_with_queries(self):
        """
        Analyses model object's fact name and query fields to determine logic for generating the data.

        If fact name present, query field is ignored and problem is regarded as multi-class classification task.
        Each value for fact name is regarded as separate class.

        If fact name not present, query is used to determine "positive" exmples and "negative" examples
        are determined automatically. This is now a binary classification problem.

        :return: list of class names, list of queries
        """
        fact_name = None
        min_count = 0
        if hasattr(self.tagger_object, 'fact_name'):
            fact_name = self.tagger_object.fact_name
        query = json.loads(self.tagger_object.query)
        if fact_name:
            # retrieve class names using fact_name field
            if hasattr(self.tagger_object, 'minimum_sample_size'):
                min_count = self.tagger_object.minimum_sample_size
            class_names = self._get_tags(fact_name, min_count)
            queries = self._create_queries(fact_name, class_names, query)
        else:
            # use description as class name for binary decisions
            class_names = ['true']
            # if fact name not present, use query provided
            queries = [query]
        return class_names, queries


    def _get_tags(self, fact_name, min_count=50, max_count=None):
        """Finds possible tags for training by aggregating active project's indices."""
        active_indices = self.tagger_object.get_indices()
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
            samples[class_name] = self._get_class_sample(self.queries[i], class_name)
        # if only one class, add negatives automatically
        # add negatives as additional class if asked
        if len(self.class_names) < 2 or self.add_negative_sample:
            self.show_progress.update_step("scrolling negative sample")
            self.show_progress.update_view(0)
            # set size of negatives equal to first class examples len
            size = len(samples[self.class_names[0]])
            samples['false'] = self._get_negatives(size)
        return samples


    def _get_class_sample(self, query, class_name):
        """Returns sample for given class"""
        # limit the docs according to max sample size & feedback size
        limit = int(self.tagger_object.maximum_sample_size)
        if class_name in self.feedback:
            limit = limit - len(self.feedback[class_name])
        # iterator for retrieving positive sample by query
        positive_sample_iterator = ElasticSearcher(
            query=query,
            indices=self.indices,
            field_data=self.fields_with_language,
            output=ElasticSearcher.OUT_DOC_WITH_ID,
            callback_progress=self.show_progress,
            scroll_limit=limit,
            text_processor=self.text_processor
        )
        positive_sample = []
        # set positive ids to ignore while scrolling for negatives
        for doc in positive_sample_iterator:
            self.ignore_ids.add(doc["_id"])
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
            model_object=self.tagger_object,
            prediction_to_match=prediction_to_match,
            text_processor=self.text_processor,
            callback_progress=self.show_progress,
        )
        # iterator to list
        feedback_sample = list(feedback_sample)
        feedback_sample_content = []
        # set positive ids to ignore while scrolling for negatives
        for doc in feedback_sample:
            self.ignore_ids.add(doc["_id"])
            content = json.loads(doc['content'])
            feedback_sample_content.append(content)
        if self.join_fields:
            feedback_sample_content = self._join_fields(feedback_sample_content)
        return feedback_sample_content


    def _get_negatives(self, size):
        self.show_progress.update_step("scrolling negative sample")
        self.show_progress.update_view(0)
        # iterator for retrieving negative examples
        negative_sample_iterator = ElasticSearcher(
            indices=self.indices,
            field_data=self.fields_with_language,
            output=ElasticSearcher.OUT_DOC,
            callback_progress=self.show_progress,
            text_processor=self.text_processor,
            scroll_limit=size * int(self.tagger_object.negative_multiplier),
            ignore_ids=self.ignore_ids,
        )
        # iterator to list
        negative_sample = list(negative_sample_iterator)
        # document doct to value string if asked
        if self.join_fields:
            negative_sample = self._join_fields(negative_sample)
        return negative_sample


    def _validate(self):
        """Validates self.data after creation."""
        # check if enough classes
        if len(self.data.keys()) < 2:
            raise InvalidDataSampleError("Data sample has less than 2 classes! Check your data!")
        # check if each class has data
        for k, v in self.data.items():
            if not v:
                raise InvalidDataSampleError(f"Class '{k}' in data sample has no examples! Check your data!")
        return True
