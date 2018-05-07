# -*- coding: utf8 -*-

import json
import re
import string

import numpy as np

from utils.datasets import Datasets
from utils.es_manager import ES_Manager


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


class esIteratorError(Exception):
    """ esIterator Exception
    """
    pass


class Lexicon:

    def __init__(self, reduction_methods):
        self.punct_re = re.compile('[%s]' % re.escape(string.punctuation))
        self.reduction_methods = reduction_methods

    def lexicon_reduction(self, doc_text):
        if not isinstance(doc_text, str):
            doc_text = unicode(doc_text).encode('utf8')
        sentences = doc_text.split('\n')
        if u'remove_numbers' in self.reduction_methods:
            sentences = [re.sub('(\d)+', 'n', sentence) for sentence in sentences]
        if u'remove_punctuation' in self.reduction_methods:
            sentences = [self.punct_re.sub('[punct]', sentence) for sentence in sentences]
        doc_text = ' '.join(sentences)
        return doc_text


class EsDataSample(object):

    def __init__(self, query, field, request):
        self.field = field
        self.request = request
        reduction_methods = self.request.POST.getlist('lexicon_reduction[]')
        self.lexicon = Lexicon(reduction_methods)
        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        self.es_m = ds.build_manager(ES_Manager)
        self.es_m.load_combined_query(query)

    def _get_positive_samples(self, sample_size):
        positive_samples = []
        positive_set = set()

        self.es_m.set_query_parameter('size', 100)
        response = self.es_m.scroll()
        scroll_id = response['_scroll_id']
        l = response['hits']['total']
        while l > 0 and len(positive_samples) <= sample_size:

            response = self.es_m.scroll(scroll_id=scroll_id)
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'],
                                                                              response['timed_out'], response['took'])
                raise esIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]
                    doc_text = self.lexicon.lexicon_reduction(decoded_text)
                    doc_id = str(hit['_id'])
                    positive_samples.append(doc_text)
                    positive_set.add(doc_id)
                except KeyError as e:
                    # If the field is missing from the document
                    pass

        return positive_samples, positive_set

    def _get_negative_samples(self, positive_set):
        negative_samples = []
        response = self.es_m.scroll(match_all=True)
        scroll_id = response['_scroll_id']
        l = response['hits']['total']
        sample_size = len(positive_set)

        while l > 0 and len(negative_samples) <= sample_size:

            response = self.es_m.scroll(scroll_id=scroll_id)
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'],
                                                                              response['timed_out'], response['took'])
                raise esIteratorError(msg)

            for hit in response['hits']['hits']:
                try:
                    doc_id = str(hit['_id'])
                    if doc_id in positive_set:
                        continue
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]
                    doc_text = self.lexicon.lexicon_reduction(decoded_text)
                    negative_samples.append(doc_text)
                except KeyError as e:
                    # If the field is missing from the document
                    pass

        return negative_samples

    def get_data_samples(self, sample_size=MAX_POSITIVE_SAMPLE_SIZE):
        positive_samples, positive_set = self._get_positive_samples(sample_size)
        negative_samples = self._get_negative_samples(positive_set)        

        data_sample_x = np.asarray(positive_samples + negative_samples)
        data_sample_y = np.asarray([1] * len(positive_samples) + [0] * len(negative_samples))

        statistics = {}
        statistics['total_positive'] = len(positive_samples)
        statistics['total_negative'] = len(negative_samples)
        return data_sample_x, data_sample_y, statistics


class EsDataClassification(object):

    def __init__(self, es_index, es_mapping, field, query):
        # Dataset info
        self.es_index = es_index
        self.es_mapping = es_mapping
        self.field = field
        # Build ES manager
        self.es_m = ES_Manager(es_index, es_mapping)
        self.es_m.load_combined_query(query)

    def get_total_documents(self):
        return self.es_m.get_total_documents()

    def get_tags_by_id(self, doc_id):
        request_url = '{0}/{1}/{2}/{3}'.format(self.es_m.es_url, self.es_index, self.es_mapping, doc_id)
        response = ES_Manager.plain_get(request_url)
        if 'texta_tags' in response['_source']:
            tags = response['_source']['texta_tags']
        else:
            tags = ""
        return tags.split()

    def apply_classifiers(self, classifiers, classifier_tags):
        if not isinstance(classifiers, list):
            classifiers = [classifiers]

        if not isinstance(classifier_tags, list):
            classifier_tags = [classifier_tags]

        response = self.es_m.scroll()
        scroll_id = response['_scroll_id']
        total_hits = response['hits']['total']
        total_processed = 0
        positive_docs = []
        positive_docs_batch = []
        batch_size = 1000

        # Get all positive documents
        while total_hits > 0:

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'],
                                                                              response['timed_out'], response['took'])
                raise esIteratorError(msg)

            for hit in response['hits']['hits']:
                positive_docs_batch.append(((str(hit['_id'])), hit['_source']))

                if len(positive_docs_batch) >= batch_size:
                    positive_docs_per_classifier = self._apply_classifiers_to_documents(positive_docs_batch, classifiers, classifier_tags)
                    positive_docs_batch = []
                    total_processed += len(positive_docs_batch)

            # New scroll request
            response = self.es_m.scroll(scroll_id=scroll_id)
            total_hits = len(response['hits']['hits'])

        if positive_docs_batch:
            positive_docs_per_classifier = self._apply_classifiers_to_documents(
                positive_docs_batch, classifiers, classifier_tags)
            total_processed += len(positive_docs_batch)

        data = {}
        data['total_processed'] = total_processed
        data['total_positive'] = positive_docs_per_classifier[0] if len(classifiers) == 1 else positive_docs_per_classifier
        if len(classifiers) == 1:
            data['total_negative'] = total_processed - positive_docs_per_classifier[0]
        else:
            data['total_negative'] = [
                total_processed - positive_docs_count for positive_docs_count in positive_docs_per_classifier
            ]
        data['total_documents'] = self.get_total_documents()

        return data

    def _apply_classifiers_to_documents(self, documents, classifiers, classifier_tags):
        """
        :param documents: list of (doc_id, document) entries
        :return: None
        """
        field_path_components = self.field.split('.')
        fields_data = []

        for document in documents:
            # Traverse the nested fields to reach the sought input text/data for the classifier
            field_data = document[1]
            for field_path_component in field_path_components:
                field_data = field_data[field_path_component]
            fields_data.append(field_data)

        positive_docs = []
        classifiers_predictions = []

        for classifier in classifiers:
            predictions = classifier.predict(fields_data)
            classifiers_predictions.append(predictions)
            positive_docs.append(sum(predictions))

        bulk_update_content = []
        for document_idx, document in enumerate(documents):
            document_id, document = document
            if 'texta_tags' in document:
                tags = set([tag.strip() for tag in document['texta_tags'].split('\n')])
            else:
                tags = set()

            new_tags = False
            for classifier_idx, classifier_predictions in enumerate(classifiers_predictions):
                if classifier_predictions[document_idx] == 1:
                    tag_count_before = len(tags)
                    tags.add(classifier_tags[classifier_idx])
                    new_tags = len(tags) > tag_count_before

            if new_tags:
                bulk_update_content.append(json.dumps({
                    'update': {
                        '_id': document_id,
                        '_index': self.es_index,
                        '_type': self.es_mapping
                    }
                }))
                bulk_update_content.append(json.dumps({
                    'doc': {
                        'texta_tags': '\n'.join(sorted(tags))
                    }
                }))

        bulk_update_content.append('')
        bulk_update_content = '\n'.join(bulk_update_content)

        self.es_m.plain_post_bulk(self.es_m.es_url, bulk_update_content)

        return positive_docs


def classify_documents(documents, classifiers, classifier_tags, field_paths):
    field_paths_components = [field_path.split('.') for field_path in field_paths]
    fields_data = [[] for _ in range(len(classifiers))]

    for document in documents:
        for classifier_idx, field_path_components in enumerate(field_paths_components):
            # Traverse the nested fields to reach the sought input text/data for the classifier
            field_data = document[1]
            for field_path_component in field_path_components:
                field_data = field_data[field_path_component]
            fields_data[classifier_idx].append(field_data)

    classifiers_predictions = []
    for classifier_idx, classifier in enumerate(classifiers):
        predictions = classifier.predict(fields_data[classifier_idx])
        classifiers_predictions.append(predictions)

    for document_idx, document in enumerate(documents):
        if 'texta_tags' in document:
            tags = set([tag.strip() for tag in document['texta_tags'].split('\n')])
        else:
            tags = set()

        new_tags = False
        for classifier_idx, classifier_predictions in enumerate(classifiers_predictions):
            if classifiers_predictions[document_idx] == 1:
                tag_count_before = len(tags)
                tags.add(classifier_tags[classifier_idx])
                new_tags = len(tags) > tag_count_before

        if new_tags:
            document['texta_tags'] = '\n'.join(sorted(tags))

    return documents
