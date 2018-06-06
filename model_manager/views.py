# -*- coding: utf8 -*-
from __future__ import print_function
import json
import logging
import os
import re
import string

import platform
if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process

from datetime import datetime

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.utils.encoding import smart_str
from gensim.models import word2vec

from searcher.models import Search
from lm.views import model_manager as lm_model_manager
from model_manager.models import ModelRun
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import STATIC_URL, URL_PREFIX, MODELS_DIR, INFO_LOGGER, ERROR_LOGGER


def get_fields(es_m):
    """ Create field list from fields in the Elasticsearch mapping
    """
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for data in mapped_fields:
        print(data)
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
@permission_required('model_manager.change_modelrun')
def index(request):

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    fields = get_fields(es_m)

    template = loader.get_template('model_manager.html')
    return HttpResponse(template.render({'searches': Search.objects.filter(author=request.user,dataset=Dataset(pk=int(request.session['dataset']))),
                                         'STATIC_URL': STATIC_URL,
                                         'runs': ModelRun.objects.all().order_by('-pk'),
                                         'fields': fields}, request))


@login_required
@permission_required('model_manager.change_modelrun')
def delete_model(request):
    model_id = request.GET['model_id']
    run = ModelRun.objects.get(pk=model_id)
    if run.user == request.user or request.user.is_superuser:
        lm_model_manager.remove_model(run.pk)
        run.delete()
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DELETE MODEL','event':'model_deleted','args':{'user_name':request.user.username,'model_id':model_id}}))
    else:
        logging.getLogger(INFO_LOGGER).warning(json.dumps({'process':'DELETE MODEL','event':'model_deletion_failed','args':{'user_name':request.user.username,'model_id':model_id},'reason':"Created by someone else."}))

    return HttpResponseRedirect(URL_PREFIX + '/model_manager')


@login_required
@permission_required('model_manager.change_modelrun')
def start_training_job(request):
    num_dimensions = int(request.POST['num_dimensions'])
    num_workers = int(request.POST['num_workers'])
    description = request.POST['description']
    mapped_field = request.POST['field']
    mapped_field = json.loads(mapped_field)
    field_path = mapped_field['path']
    min_freq = int(request.POST['min_freq'])
    search_id = request.POST['search']

    train_model(search_id,field_path,num_dimensions,num_workers,min_freq,request.user,description,request)
    #Process(target=train_model,args=(search_id,field_path,num_dimensions,num_workers,min_freq,request.user,description,request)).start()
    return HttpResponse()


def train_model(search_id,field_path,num_dimensions,num_workers,min_freq,usr,description,request):

    # select search
    if search_id == 'all_docs':
        query = {"main":{"query":{"bool":{"minimum_should_match":0,"must":[],"must_not":[],"should":[]}}}}
    else:
        query = json.loads(Search.objects.get(pk=int(search_id)).query)

    # add Run to db
    dataset_pk = int(request.session['dataset'])

    model_status = 'running'

    new_run = ModelRun(run_description=description,
                       min_freq=min_freq,
                       num_dimensions=num_dimensions,
                       num_workers=num_workers,
                       fields=field_path,
                       search=json.dumps(query), run_status=model_status,
                       run_started=datetime.now(), run_completed=None, user=usr)
    new_run.save()

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_started',
                                                    'args': {'user_name': request.user.username, 'search_id': search_id,
                                                             'field': field_path, 'num_dimensions': num_dimensions,
                                                             'num_workers': num_workers, 'min_freq': min_freq,
                                                             'desc': description}, 'data': {'run_id': new_run.id}}))
    print('Run added to db.')

    num_passes = 5
    # Number of word2vec passes + one pass to vocabulary building
    total_passes = num_passes + 1
    show_progress = ShowProgress(new_run.pk, multiplier=total_passes)
    show_progress.update_view(0)

    model = word2vec.Word2Vec()

    try:
        sentences = esIterator(query, field_path, request, callback_progress=show_progress)

        model = word2vec.Word2Vec(sentences, min_count=min_freq,
                                  size=num_dimensions,
                                  workers=num_workers,
                                  iter=num_passes)

        model_name = 'model_' + str(new_run.pk)
        output_model_file = os.path.join(MODELS_DIR, model_name)
        model.save(output_model_file)
        model_status = 'completed'

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE MODEL','event':'model_training_failed','args':{'user_name':request.user.username}}),exc_info=True)
        print('--- Error: {0}'.format(e))
        model_status = 'failed'

    #lm_model_manager.add_model(str(new_run.pk),model)

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL',
                                                    'event': 'model_training_completed',
                                                    'args': {'user_name': request.user.username},
                                                    'data': {'run_id': new_run.id}}))
    # declare the job done
    r = ModelRun.objects.get(pk=new_run.pk)
    r.run_completed = datetime.now()
    r.run_status = model_status
    r.lexicon_size = len(model.wv.vocab)
    r.save()
    print('job is done')

@login_required
@permission_required('model_manager.change_modelrun')
def download_model(request):
    model_id = request.GET['model_id']

    file_path = os.path.join(MODELS_DIR, "model_" + str(model_id))
    if os.path.exists(file_path):
        with open(file_path, 'rb') as fh:
            response = HttpResponse(fh)
            response['Content-Disposition'] = 'attachment; filename=' + os.path.basename(file_path)
            return response

    return HttpResponseRedirect(URL_PREFIX + '/model_manager')

class ShowProgress(object):
    """ Show model training progress
    """
    def __init__(self, model_pk, multiplier=None):
        self.n_total = None
        self.n_count = 0
        self.model_pk = model_pk
        self.multiplier = multiplier

    def set_total(self, total):
        self.n_total = total
        if self.multiplier:
            self.n_total = self.multiplier*total

    def update(self, amount):
        if amount == 0:
            return
        self.n_count += amount
        percentage = (100.0*self.n_count)/self.n_total
        self.update_view(percentage)

    def update_view(self, percentage):
        r = ModelRun.objects.get(pk=self.model_pk)
        r.run_status = 'running [{0:3.0f} %]'.format(percentage)
        r.save()


class esIteratorError(Exception):
    """ esIterator Exception
    """
    pass


class esIterator(object):
    """  ElasticSearch Iterator
    """

    def __init__(self, query, field, request, callback_progress=None):
        self.field = field
        self.request = request
        self.punct_re = re.compile('[%s]' % re.escape(string.punctuation))

        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        self.es_m = ds.build_manager(ES_Manager)
        self.es_m.load_combined_query(query)

        self.callback_progress = callback_progress

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)

    def __iter__(self):

        self.es_m.set_query_parameter('size', 100)
        response = self.es_m.scroll()

        scroll_id = response['_scroll_id']
        l = response['hits']['total']

        while l > 0:
            response = self.es_m.scroll(scroll_id=scroll_id)
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'], response['timed_out'], response['took'])
                raise esIteratorError(msg)

            for hit in response['hits']['hits']:

                try:
                    # Take into account nested fields encoded as: 'field.sub_field'
                    decoded_text = hit['_source']
                    for k in self.field.split('.'):
                        decoded_text = decoded_text[k]
                    sentences = decoded_text.split('\n')
                    reduction_methods = self.request.POST.getlist('lexicon_reduction[]')
                    if u'remove_numbers' in reduction_methods:
                        # remove numbers
                        sentences = [re.sub('(\d)+','n',sentence) for sentence in sentences]
                    if u'remove_punctuation' in reduction_methods:
                        # remove punctuation
                        sentences = [self.punct_re.sub('[punct]',sentence) for sentence in sentences]
                    for sentence in sentences:
                        yield [smart_str(word.strip().lower()) for word in sentence.split(' ')]
                except:
                    # If the field is missing from the document
                    KeyError

            if self.callback_progress:
                self.callback_progress.update(l)

    def get_total_documents(self):
        return self.es_m.get_total_documents()
