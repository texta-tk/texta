# -*- coding: utf8 -*-
import json
import logging
import os
import re
import string
import threading
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from corpus_tool.models import Search
from lm.views import model_manager as lm_model_manager
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import STATIC_URL, URL_PREFIX, MODELS_DIR, INFO_LOGGER, ERROR_LOGGER

import numpy as np

from classification_manager.models import ModelClassification
from classification_manager import model_pipeline


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


@login_required
def index(request):

    context = {}

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    fields = get_fields(es_m)

    context['searches'] = Search.objects.filter(author=request.user,
                                                dataset=Dataset(pk=int(request.session['dataset'])))
    context['STATIC_URL'] = STATIC_URL
    context['runs'] = ModelClassification.objects.all().order_by('-pk')
    context['fields'] = fields

    pipe_builder = model_pipeline.get_pipeline_builder()
    context['extractor_opt_list'] = pipe_builder.get_extractor_options()
    context['reductor_opt_list'] = pipe_builder.get_reductor_options()
    context['normalizer_opt_list'] = pipe_builder.get_normalizer_options()
    context['classifier_opt_list'] = pipe_builder.get_classifier_options()

    template = loader.get_template('classification_manager.html')
    return HttpResponse(template.render(context, request))


@login_required
def delete_model(request):
    model_id = request.GET['model_id']
    run = ModelClassification.objects.get(pk=model_id)
    if run.user == request.user or request.user.is_superuser:
        lm_model_manager.remove_model(run.pk)
        run.delete()
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DELETE MODEL','event':'model_deleted','args':{'user_name':request.user.username,'model_id':model_id}}))
    else:
        logging.getLogger(INFO_LOGGER).warning(json.dumps({'process':'DELETE MODEL','event':'model_deletion_failed','args':{'user_name':request.user.username,'model_id':model_id},'reason':"Created by someone else."}))
        
    return HttpResponseRedirect(URL_PREFIX + '/classification_manager')

from multiprocessing import Process

@login_required
def start_training_job(request):

    search_id = int(request.POST['search'])
    mapped_field = request.POST['field']
    mapped_field = json.loads(mapped_field)
    field_path = mapped_field['path']
    extractor_opt = int(request.POST['extractor_opt'])
    reductor_opt = int(request.POST['reductor_opt'])
    normalizer_opt = int(request.POST['normalizer_opt'])
    classifier_opt = int(request.POST['classifier_opt'])
    description = request.POST['description']

    usr = request.user

    print '---> Start model training: ', search_id, field_path
    print '---> Param: ', (extractor_opt, reductor_opt, normalizer_opt, classifier_opt)

    clf_args = (request, usr, search_id, field_path, extractor_opt, reductor_opt,
                normalizer_opt, classifier_opt, description)

    # clf_job = threading.Thread( target=train_classifier, args=clf_args)
    # clf_job.start()

    clf_job = Process(target=train_classifier, args=clf_args)
    clf_job.start()

    return HttpResponse()


def train_classifier(request, usr, search_id, field_path, extractor_opt, reductor_opt,
                     normalizer_opt, classifier_opt, description):

    # add Run to db
    dataset_pk = int(request.session['dataset'])
    model_status = 'running'
    model_score = "---"
    clf_arch = "---"

    new_run = ModelClassification(run_description=description, fields=field_path, score=model_score,
                                  search=Search.objects.get(pk=search_id).query, run_status=model_status,
                                  run_started=datetime.now(), run_completed=None, user=usr, clf_arch=clf_arch)
    new_run.save()

    print 'Run added to db.'
    query = json.loads(Search.objects.get(pk=search_id).query)
    steps = ["preparing data", "training", "done"]
    show_progress = ShowSteps(new_run.pk, steps)
    show_progress.update_view()

    try:

        show_progress.update(0)
        pipe_builder = model_pipeline.get_pipeline_builder()
        pipe_builder.set_pipeline_options(extractor_opt, reductor_opt, normalizer_opt, classifier_opt)
        clf_arch = pipe_builder.pipeline_representation()
        c_pipe, params = pipe_builder.build()

        print '---> Here is ok? ', params

        es_data = EsData(query, field_path, request)
        data_sample_x, data_sample_y = es_data.get_data_samples()

        show_progress.update(1)
        model, score, training_log = model_pipeline.train_model_with_cv(c_pipe, params, data_sample_x, data_sample_y)

        model_score = "{0:.2f}".format(score['f1_score'])
        show_progress.update(2)
        model_name = 'classifier_{0}.pkl'.format(new_run.pk)
        output_model_file = os.path.join(MODELS_DIR, model_name)
        model_pipeline.save_model(model, output_model_file)
        model_status = 'completed'

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE MODEL','event':'model_training_failed','args':{'user_name':request.user.username}}),exc_info=True)
        print '--- Error: {0}'.format(e)
        model_status = 'failed'

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL',
                                                    'event': 'model_training_completed',
                                                    'args': {'user_name': request.user.username},
                                                    'data': {'run_id': new_run.id}}))
    # declare the job done
    r = ModelClassification.objects.get(pk=new_run.pk)
    r.run_completed = datetime.now()
    r.run_status = model_status
    r.score = model_score
    r.clf_arch = clf_arch
    r.save()

    print 'job is done'


class ShowSteps(object):
    """ Show model training progress
    """
    def __init__(self, model_pk, steps):
        self.step_messages = steps
        self.n_total = len(steps)
        self.n_step = 0
        self.model_pk = model_pk

    def update(self, step):
        self.n_step = step
        self.update_view()

    def update_view(self):
        i = self.n_step
        r = ModelClassification.objects.get(pk=self.model_pk)
        r.run_status = '{0} [{1}/{2}]'.format(self.step_messages[i], i+1, self.n_total)
        r.save()


def test_model(request):
    print '---> Test model ... '
    return HttpResponse()


class esIteratorError(Exception):
    """ esIterator Exception
    """
    pass


class EsData(object):

    def __init__(self, query, field, request):
        self.field = field
        self.request = request
        self.punct_re = re.compile('[%s]' % re.escape(string.punctuation))

        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        self.es_m = ds.build_manager(ES_Manager)
        self.es_m.load_combined_query(query)

    def _lexicon_reduction(self, doc_text):
        sentences = doc_text.split('\n')
        reduction_methods = self.request.POST.getlist('lexicon_reduction[]')

        if u'remove_numbers' in reduction_methods:
            sentences = [re.sub('(\d)+', 'n', sentence) for sentence in sentences]

        if u'remove_punctuation' in reduction_methods:
            sentences = [self.punct_re.sub('[punct]', sentence) for sentence in sentences]

        doc_text = ' '.join(sentences)
        return doc_text

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
                    doc_text = self._lexicon_reduction(decoded_text)
                    doc_id = str(hit['_id'])
                    positive_samples.append(doc_text)
                    positive_set.add(doc_id)
                except KeyError as e:
                    # If the field is missing from the document
                    pass
        print '---> Total positive_samples: ', len(positive_samples)
        return positive_samples, positive_set

    def _get_negative_samples(self, positive_set):
        negative_samples = []
        response = self.es_m.scroll_all_match()
        scroll_id = response['_scroll_id']
        l = response['hits']['total']
        sample_size = len(positive_set)

        while l > 0 and len(negative_samples) <= sample_size:

            response = self.es_m.scroll_all_match(scroll_id=scroll_id)
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
                    doc_text = self._lexicon_reduction(decoded_text)
                    negative_samples.append(doc_text)
                except KeyError as e:
                    # If the field is missing from the document
                    pass
        print '---> Total negative_samples: ', len(negative_samples)
        return negative_samples

    def get_data_samples(self, sample_size=10000):
        positive_samples, positive_set = self._get_positive_samples(sample_size)
        negative_samples = self._get_negative_samples(positive_set)
        data_sample_x = np.asarray(positive_samples + negative_samples)
        data_sample_y = np.asarray([1] * len(positive_samples) + [0] * len(negative_samples))
        return data_sample_x, data_sample_y