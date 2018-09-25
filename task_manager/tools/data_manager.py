# -*- coding: utf8 -*-
import json
import logging

from searcher.models import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from texta.settings import ERROR_LOGGER

MAX_POSITIVE_SAMPLE_SIZE = 10000


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


class EsIteratorError(Exception):
    """ EsIterator Exception
    """
    pass


class EsIterator:
    """  ElasticSearch Iterator
    """

    def __init__(self, parameters, callback_progress=None):
        ds = Datasets().activate_dataset_by_id(parameters['dataset'])
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
        self.es_m.set_query_parameter('size', 500)
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
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]
                    sentences = decoded_text.split('\n')
                    for sentence in sentences:
                        yield [word.strip().lower() for word in sentence.split(' ')]

                except KeyError:
                    # If the field is missing from the document
                    logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})

            if self.callback_progress:
                self.callback_progress.update(total_hits)

    def get_total_documents(self):
        return self.es_m.get_total_documents()


class EsDataSample(object):

    def __init__(self, field, query, es_m):
        """ Sample data - Positive and Negative samples from query
        """
        self.field = field
        self.es_m = es_m
        self.es_m.load_combined_query(query)

    def _get_positive_samples(self, sample_size):
        positive_samples = []
        positive_set = set()

        self.es_m.set_query_parameter('size', 100)
        response = self.es_m.scroll()
        scroll_id = response['_scroll_id']
        total_hits = response['hits']['total']
        while total_hits > 0 and len(positive_samples) <= sample_size:

            response = self.es_m.scroll(scroll_id=scroll_id)
            total_hits = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'],
                                                                              response['timed_out'], response['took'])
                raise EsIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]

                    doc_id = str(hit['_id'])
                    positive_samples.append(decoded_text)
                    positive_set.add(doc_id)

                except KeyError as e:
                    # If the field is missing from the document
                    logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
                    pass

        return positive_samples, positive_set

    def _get_negative_samples(self, positive_set):
        negative_samples = []
        response = self.es_m.scroll(match_all=True)
        scroll_id = response['_scroll_id']
        hit_length = response['hits']['total']
        sample_size = len(positive_set)

        while hit_length > 0 and len(negative_samples) <= sample_size:

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
                    doc_id = str(hit['_id'])
                    if doc_id in positive_set:
                        continue
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]

                    negative_samples.append(decoded_text)
                except KeyError as e:
                    # If the field is missing from the document
                    logging.getLogger(ERROR_LOGGER).error('Key does not exist.', exc_info=True, extra={'hit': hit, 'scroll_response': response})
                    pass

        return negative_samples

    def get_data_samples(self, sample_size=MAX_POSITIVE_SAMPLE_SIZE):
        positive_samples, positive_set = self._get_positive_samples(sample_size)
        negative_samples = self._get_negative_samples(positive_set)

        data_sample_x = positive_samples + negative_samples
        data_sample_y = [1] * len(positive_samples) + [0] * len(negative_samples)

        statistics = {}
        statistics['total_positive'] = len(positive_samples)
        statistics['total_negative'] = len(negative_samples)
        return data_sample_x, data_sample_y, statistics
