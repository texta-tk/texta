# -*- coding: utf8 -*-
import json
import logging

from searcher.models import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import ERROR_LOGGER

MAX_POSITIVE_SAMPLE_SIZE = 10000
ES_SCROLL_SIZE = 5000


def get_fields(es_m):
    """ Crete field list from fields in the Elasticsearch mapping
    """
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for data in mapped_fields:
        path = data['path']
        path_list = path.split('.')
        label = '{0} --> {1}'.format(path_list[0], ' --> '.join(path_list[1:])) if len(path_list) > 1 else path_list[0]
        label = label.replace('-->', u'→')
        field = {'data': json.dumps(data), 'label': label}
        fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])

    return fields


class TaskCanceledException(Exception):
    """ Task Canceled Exception
    """
    pass


class EsIteratorError(Exception):
    """ EsIterator Exception
    """
    pass


class EsIterator:
    """  ElasticSearch Iterator
    """

    def __init__(self, parameters, callback_progress=None):
        ds = Datasets().activate_datasets_by_id(parameters['dataset'])
        query = self._parse_query(parameters)

        # self.field = json.loads(parameters['field'])['path']
        self.field = parameters['field']
        self.es_m = ds.build_manager(ES_Manager)
        self.es_m.load_combined_query(query)
        self.callback_progress = callback_progress

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)

    @staticmethod
    def _parse_query(parameters):
        search = parameters['search']
        # select search
        if search == 'all_docs':
            query = {"main": {"query": {"bool": {"minimum_should_match": 0, "must": [], "must_not": [], "should": []}}}}
        else:
            query = json.loads(Search.objects.get(pk=int(search)).query)
        return query

    def __iter__(self):
        self.es_m.set_query_parameter('size', ES_SCROLL_SIZE)
        response = self.es_m.scroll()

        scroll_id = response['_scroll_id']
        total_hits = response['hits']['total']

        while total_hits > 0:
            response = self.es_m.scroll(scroll_id=scroll_id)
            total_hits = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'], response['timed_out'], response['took'])
                raise EsIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        # get nested fields encoded as: 'field.sub_field'
                        decoded_text = decoded_text[k]
                    
                    if decoded_text:
                        sentences = decoded_text.split('\n')
                        for sentence in sentences:
                            yield [word.strip().lower() for word in sentence.split(' ')]

                except KeyError:
                    # If the field is missing from the document
                    logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})

                except TypeError:
                    # If split failed
                    logging.getLogger(ERROR_LOGGER).error('Error splitting the text.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
            
            if self.callback_progress:
                self.callback_progress.update(total_hits)

    def get_total_documents(self):
        return self.es_m.get_total_documents()


class EsDataSample(object):

    def __init__(self, fields, query, es_m, negative_set_multiplier=1.0, max_positive_sample_size=MAX_POSITIVE_SAMPLE_SIZE, score_threshold=0.0):
        """ Sample data - Positive and Negative samples from query
        negative_set_multiplier (float): length of positive set is multiplied by this to determine negative sample size (to over- or underfit models)
        max_positive_sample_size (int): maximum number of documents per class used to train the model
        score_threshold (float): hits' max_score is multiplied by this to determine the score cutoff point (lowest allowed score) , value between 0.0 and 1.0
        """
        self.fields = fields
        self.es_m = es_m
        self.es_m.load_combined_query(query)
        self.negative_set_multiplier = negative_set_multiplier
        self.max_positive_sample_size = max_positive_sample_size
        self.score_threshold = score_threshold

    def _get_positive_samples(self, sample_size):
        
        positive_samples_map = {}
        positive_set = set()
        # Initialize sample map
        for field in self.fields:
            positive_samples_map[field] = []

        self.es_m.set_query_parameter('size', ES_SCROLL_SIZE)
        response = self.es_m.scroll()
        scroll_id = response['_scroll_id']
        total_hits = response['hits']['total']
        while total_hits > 0 and len(positive_set) <= sample_size:

            response = self.es_m.scroll(scroll_id=scroll_id)
            total_hits = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'],
                                                                              response['timed_out'], response['took'])
                raise EsIteratorError(msg)

            lowest_allowed_score = response['hits']['max_score'] * self.score_threshold

            # Iterate over all docs
            for hit in response['hits']['hits']:
                if hit['_score'] >= lowest_allowed_score:
                    try:
                        for field in self.fields:
                            # Extract text content for every field
                            _temp_text = hit['_source']
                            for k in field.split('.'):
                                # Get nested fields encoded as: 'field.sub_field'
                                try:
                                    _temp_text = _temp_text[k]
                                except Exception:
                                    logging.getLogger(ERROR_LOGGER).error('Field not present in document.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
                                    _temp_text = ''
                                # sanity check to remove None values
                                if not _temp_text:
                                    _temp_text = ''
                            # Save decoded text into positive sample map
                            positive_samples_map[field].append(_temp_text)
                        
                        # Save sampled doc id
                        doc_id = str(hit['_id'])
                        positive_set.add(doc_id)

                    except KeyError as e:
                        # If the field is missing from the document
                        logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
                else:
                    break

        return positive_samples_map, positive_set

    def _get_negative_samples(self, positive_set):

        negative_samples_map = {}
        negative_set = set()
        # Initialize sample map
        for field in self.fields:
            negative_samples_map[field] = []

        self.es_m.set_query_parameter('size', ES_SCROLL_SIZE)
        response = self.es_m.scroll(match_all=True)
        scroll_id = response['_scroll_id']
        hit_length = response['hits']['total']
        sample_size = len(positive_set)

        while hit_length > 0 and len(negative_set) <= sample_size:

            response = self.es_m.scroll(scroll_id=scroll_id)
            hit_length = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'],
                                                                              response['timed_out'], response['took'])
                raise EsIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    # Get doc id
                    doc_id = str(hit['_id'])
                    if doc_id in positive_set:
                        # If used already, continue
                        continue
                    # Otherwise, consider as negative sample
                    negative_set.add(doc_id)

                    for field in self.fields:
                        # Extract text content for every field
                        _temp_text = hit['_source']
                        for k in field.split('.'):
                            # Get nested fields encoded as: 'field.sub_field'
                            try:
                                _temp_text = _temp_text[k]
                            except Exception:
                                logging.getLogger(ERROR_LOGGER).error('Field not present in document.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
                                _temp_text = ''
                            # sanity check to remove None values
                            if not _temp_text:
                                _temp_text = ''
                        # Save decoded text into positive sample map
                        negative_samples_map[field].append(_temp_text)

                except KeyError as e:
                    # If the field is missing from the document
                    logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})

        return negative_samples_map, negative_set

    def get_data_samples(self, sample_size=MAX_POSITIVE_SAMPLE_SIZE):

        positive_samples, positive_set = self._get_positive_samples(sample_size)
        negative_samples, negative_set = self._get_negative_samples(positive_set)

        # Build X feature map
        data_sample_x_map = {}
        for field in self.fields:
            data_sample_x_map[field] = positive_samples[field] + negative_samples[field]

        # Build target (positive + negative samples) for binary classifier
        data_sample_y = [1] * len(positive_set) + [0] * len(negative_set)

        statistics = {}
        statistics['total_positive'] = len(positive_set)
        statistics['total_negative'] = len(negative_set)
        return data_sample_x_map, data_sample_y, statistics
