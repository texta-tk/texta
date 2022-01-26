import json
import logging
from random import shuffle
from typing import List, Optional

import numpy as np
from nltk.tokenize import sent_tokenize
from texta_tools.text_processor import TextProcessor

from texta_elastic.aggregator import ElasticAggregator
from toolkit.elastic.tools.feedback import Feedback
from texta_elastic.query import Query
from texta_elastic.searcher import ElasticSearcher
from toolkit.settings import INFO_LOGGER
from toolkit.tools.lemmatizer import ElasticAnalyzer
from texta_elastic.core import ElasticCore
from ..choices import ES6_SNOWBALL_MAPPING, ES7_SNOWBALL_MAPPING
from ..exceptions import InvalidDataSampleError
from ...tools.show_progress import ShowProgress


class DataSample:
    """Re-usable object for handling positive and negative data samples for Taggers and TorchTaggers."""


    def __init__(self,
                 model_object,
                 indices: List[str],
                 field_data: List[str],
                 show_progress: ShowProgress = None,
                 join_fields: bool = False,
                 text_processor: TextProcessor = None,
                 add_negative_sample: bool = False,
                 snowball_language: str = None,
                 detect_lang: bool = False,
                 balance: bool = False,
                 use_sentence_shuffle: bool = False,
                 balance_to_max_limit: bool = False):
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
        self.field_data = self._resolve_fields(field_data)
        self.join_fields = join_fields
        self.text_processor = text_processor
        self.add_negative_sample = add_negative_sample
        self.detect_lang = detect_lang
        self.balance = balance
        self.use_sentence_shuffle = use_sentence_shuffle
        self.balance_to_max_limit = balance_to_max_limit
        self.class_display_name = None  # used for logging messages related to taggers in tagger groups
        self.max_class_size = self._get_max_class_size()
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


    def _resolve_fields(self, field_data: List[str]) -> List[str]:
        """
        Function to resolve the names of the fields that you want to exclusively fetch from
        Elasticsearch. In case of normal Taggers, getting the language field is for the sake
        of automatically detecting the language of choice for when the user wishes to apply
        Snowball stemming.

        :param field_data: List of strings containing the dot-separated names of fields.
        :return: List of fields to fetch from Elasticsearch.
        """
        if not hasattr(self.tagger_object, "snowball_language"):
            return field_data
        else:
            field_data_field = [f"{field}_mlp.language.detected" for field in field_data] + field_data
            return field_data_field


    def _get_fact_name(self):
        """ Returns fact name if it's present in
            a) Tagger object or
            b) Tagger Group object related to the Tagger object.
        """
        fact_name = None
        # if fact name is present in the tagger object
        if self.tagger_object.fact_name:
            fact_name = self.tagger_object.fact_name

        # if fact_name is present in tagger group related to the tagger object
        else:
            try:
                tagger_groups = json.loads(self.tagger_object.tagger_groups)
                fact_names = [tg.get("fact_name") for tg in tagger_groups]
                if fact_names:
                    fact_name = fact_names[0]
            # If tagger group doesn't exist in the object (e.g. Bert, Torch)
            except:
                pass
        return fact_name


    def _get_max_class_size(self) -> int:
        """Aggregates over values of the selected fact and returns the size of the largest class."""
        max_class_size = 0
        fact_name = self._get_fact_name()

        try:
            query = json.loads(self.tagger_object.query)
        except:
            query = self.tagger_object.query


        if fact_name:
            es_aggregator = ElasticAggregator(indices=self.indices, query=query)
            facts = es_aggregator.get_fact_values_distribution(fact_name=fact_name, fact_name_size=10, fact_value_size=10)
            logging.getLogger(INFO_LOGGER).info(f"Class frequencies: {facts}")
            max_class_size = max(facts.values())
        return max_class_size


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
            lemmatizer = ElasticAnalyzer()
            for cl, examples in self.data.items():
                processed_examples = []
                for example_doc in examples:
                    new_example_doc = {k: lemmatizer.stem_text(v, language=snowball_language) for k, v in example_doc.items()}
                    processed_examples.append(new_example_doc)
                self.data[cl] = processed_examples


    def _snowball_from_doc(self):
        """
        Stems the texts in data sample using Snowball.
        """
        lemmatizer = ElasticAnalyzer()
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
                                example_doc[key] = lemmatizer.stem_text(example_doc[key], snowball_language)
                processed_examples.append(example_doc)

            self.data[cl] = processed_examples


    @staticmethod
    def _join_fields(list_of_dicts):
        #return [" ".join(a.values()) for a in list_of_dicts]
        return [" ".join([str(v) for v in a.values()]) for a in list_of_dicts]


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
        try:
            query = json.loads(self.tagger_object.query)
        except:
            query = self.tagger_object.query

        if fact_name:
            # retrieve class names using fact_name field
            if hasattr(self.tagger_object, 'minimum_sample_size'):
                min_count = self.tagger_object.minimum_sample_size
            class_names = self._get_tags(fact_name, min_count, query=query)
            queries = self._create_queries(fact_name, class_names, query)
        else:
            # use description as class name for binary decisions
            class_names = ['true']
            # if fact name not present, use query provided
            queries = [query]

        return class_names, queries


    def _get_tags(self, fact_name, min_count=50, max_count=None, query={}):
        """Finds possible tags for training by aggregating active project's indices."""
        active_indices = self.tagger_object.get_indices()
        es_a = ElasticAggregator(indices=active_indices, query=query)
        # limit size to 10000 unique tags
        tag_values = es_a.facts(filter_by_fact_name=fact_name, min_count=min_count, max_count=max_count, size=10000)
        return tag_values


    def _set_class_display_name(self, class_name: str):
        """ Sets a class display name for logger messages as a plain class name ("true")
        is uniformative for taggers related to a Tagger Group.
        """
        try:
            tagger_groups = json.loads(self.tagger_object.tagger_groups)
        # If tagger group doesn't exist in the object (e.g. Bert, Torch)
        except:
            tagger_groups = []

        if tagger_groups:
            self.class_display_name = self.tagger_object.description
        else:
            self.class_display_name = class_name


    def _get_samples_for_classes(self):
        """Returns samples for each class as a dict."""
        samples = {}

        # Return empty dict, if no classes with enough number of samples is detected
        if not self.class_names:
            return samples

        for i, class_name in enumerate(self.class_names):
            self.show_progress.update_step(f"scrolling sample for {class_name}")
            self.show_progress.update_view(0)

            self._set_class_display_name(class_name)

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


    @staticmethod
    def _extract_content(doc: dict, field: str) -> str:
        """Extracts content from a potentially nested field."""
        # If field is not nested
        if field in doc:
            content = doc[field]
        else:
            content = doc
            # Retrieve text from potentially nested field
            subfields = field.split(".")
            for subfield in subfields:
                try:
                    content = content[subfield]
                except Exception as e:
                    content = ""
        return content


    @staticmethod
    def _update_content(doc: dict, field: str, content: str) -> dict:
        """Updates content of a potentially nested field."""
        # If field is not nested
        if field in doc:
            doc[field] = content
        else:
            branch = doc
            # Retrieve text from potentially nested field
            subfields = field.split(".")
            depth = len(subfields)
            for i, subfield in enumerate(subfields):
                # If reached to the deepest level, add content
                if i + 1 == depth:
                    branch[subfield] = content
                else:
                    branch = branch[subfield]
        return doc


    @staticmethod
    def _shuffle_sentences(text: str) -> str:
        """Extracts and shuffles sentences."""
        sentences = sent_tokenize(text)
        shuffle(sentences)
        shuffled_text = " ".join(sentences)
        return shuffled_text


    def _shuffle_content(self, doc: dict, fields_to_shuffle: List[str]) -> dict:
        """Shuffle sentences in field `field_to_shuffle`."""
        for field_to_shuffle in fields_to_shuffle:
            content = self._extract_content(doc, field_to_shuffle)
            shuffled_content = self._shuffle_sentences(content)
            doc = self._update_content(doc, field_to_shuffle, shuffled_content)
        return doc


    def _duplicate_examples(self, positive_sample: List[dict], class_name: str, limit: int):
        """ Generate addtional examples by duplicating them for underrepresented classes."""
        # If balancing to max limit is enabled, set the number of samples to max sample size
        if self.balance_to_max_limit:
            n_samples = limit

        # Else set the number of samples to max class size if it doesn't exceed the max sample size
        else:
            n_samples = min(self.max_class_size, limit)

        if len(positive_sample) < n_samples:
            n = n_samples - len(positive_sample)
            logging.getLogger(INFO_LOGGER).info(f"Adding {n} examples for class {self.class_display_name}")

            # Generate the required amount of additional documents by sampling with replacements
            additions = list(np.random.choice(positive_sample, size=n, replace=True))

            # If sentence shuffling is enabled, shuffle the sentences in the additional documents
            if self.use_sentence_shuffle:
                logging.getLogger(INFO_LOGGER).info(f"Shuffling sentences in additional examples of class {self.class_display_name}")
                additions = [self._shuffle_content(doc, self.field_data) for doc in additions]
            positive_sample.extend(additions)
            shuffle(positive_sample)
        return positive_sample


    def _get_class_sample(self, query, class_name):
        """Returns sample for given class"""
        # limit the docs according to max sample size & feedback size
        limit = int(self.tagger_object.maximum_sample_size)

        if class_name in self.feedback:
            limit = limit - len(self.feedback[class_name])

        logging.getLogger(INFO_LOGGER).info(f"Collecting examples for class {self.class_display_name} (max limit = {limit})...")
        # iterator for retrieving positive sample by query
        positive_sample_iterator = ElasticSearcher(
            query=query,
            indices=self.indices,
            field_data=self.field_data,
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

        logging.getLogger(INFO_LOGGER).info(f"Found {len(positive_sample)} examples for {self.class_display_name}...")

        # If class balancing is enabled, modify number of required samples
        if self.balance:
            positive_sample = self._duplicate_examples(positive_sample, class_name, limit)

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
            field_data=self.field_data,
            output=ElasticSearcher.OUT_DOC,
            callback_progress=self.show_progress,
            text_processor=self.text_processor,
            scroll_limit=int(size * float(self.tagger_object.negative_multiplier)),
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
        if not self.data:
            raise InvalidDataSampleError(f"None of the classes had enough examples (required at least {self.tagger_object.minimum_sample_size} examples per class). Try lowering the value of parameter 'minimum_sample_size'.")
        # check if enough classes
        if len(self.data.keys()) < 2:
            raise InvalidDataSampleError("Data sample has less than 2 classes! Check your data!")
        # check if each class has data
        for k, v in self.data.items():
            if not v:
                raise InvalidDataSampleError(f"Class '{k}' in data sample has no examples! Check your data!")
        return True
