# -*- coding: utf8 -*-
import json
import logging
import os
import re
import string
import threading
from datetime import datetime

import requests
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from django.utils.encoding import smart_str
from gensim.models import word2vec

from corpus_tool.models import Search
from lm.views import model_manager as lm_model_manager
from model_manager.models import ModelRun
from permission_admin.models import Dataset
from settings import STATIC_URL, es_url, URL_PREFIX, MODELS_DIR, INFO_LOGGER, ERROR_LOGGER

from utils.datasets import get_active_dataset

@login_required
@permission_required('model_manager.change_modelrun')
def index(request):    
    # Define selected mapping
    dataset,mapping,date_range = get_active_dataset(request.session['dataset'])
    
    template = loader.get_template('model_manager/model_manager_index.html')
    return HttpResponse(template.render({'searches':Search.objects.filter(author=request.user,dataset=Dataset(pk=int(request.session['dataset']))),'STATIC_URL':STATIC_URL,'runs':ModelRun.objects.all().order_by('-pk'),'fields':requests.get(es_url+'/'+dataset).json()[dataset]['mappings'][mapping]['properties']},request))

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
    field = request.POST['field']
    min_freq = int(request.POST['min_freq'])
    search_id = int(request.POST['search'])
    threading.Thread(target=train_model,args=(search_id,field,num_dimensions,num_workers,min_freq,request.user,description,request)).start()
    return HttpResponse()


def train_model(search_id,field,num_dimensions,num_workers,min_freq,usr,description,request):
    # add Run to db
    dataset_pk = int(request.session['dataset'])

    model_status = 'running'

    new_run = ModelRun(run_description=description,
                       min_freq=min_freq,
                       num_dimensions=num_dimensions,
                       num_workers=num_workers,
                       fields=field,
                       search=Search.objects.get(pk=search_id).query, run_status=model_status,
                       run_started=datetime.now(), run_completed=None, user=usr)
    new_run.save()

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process': 'CREATE MODEL', 'event': 'model_training_started',
                                                    'args': {'user_name': request.user.username, 'search_id': search_id,
                                                             'field': field, 'num_dimensions': num_dimensions,
                                                             'num_workers': num_workers, 'min_freq': min_freq,
                                                             'desc': description}, 'data': {'run_id': new_run.id}}))
    print 'Run added to db.'
    query = json.loads(Search.objects.get(pk=search_id).query)

    num_passes = 5
    # Number of word2vec passes + one pass to vocabulary building
    total_passes = num_passes + 1
    show_progress = ShowProgress(new_run.pk, multiplier=total_passes)
    show_progress.update_view(0)

    model = word2vec.Word2Vec()

    try:
        sentences = esIterator(query, field, request, callback_progress=show_progress)

        model = word2vec.Word2Vec(sentences, min_count=min_freq,
                                  size=num_dimensions,
                                  workers=num_workers,
                                  iter=num_passes)

        model_name = 'model_' + str(new_run.pk)
        output_model_file = os.path.join(MODELS_DIR, model_name)
        model.save(output_model_file)
        model_status = 'completed'

    except Exception, e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE MODEL','event':'model_training_failed','args':{'user_name':request.user.username}}),exc_info=True)
        print '--- Error: {0}'.format(e)
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
    r.lexicon_size = len(model.vocab)
    r.save()
    print 'job is done'


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
#        print('--- progress: {0:3.0f} %'.format(percentage))
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
        self.query = query
        self.field = field
        self.request = request
        self.punct_re = re.compile('[%s]' % re.escape(string.punctuation))

        # Define selected mapping
        self.datasets = get_datasets()
        self.selected_mapping = int(request.session['dataset'])
        self.dataset = self.datasets[self.selected_mapping]['index']
        self.mapping = self.datasets[self.selected_mapping]['mapping']

        self.callback_progress = callback_progress

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)

    def __iter__(self):
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=100'.format(es_url, self.dataset, self.mapping)
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(es_url)
        response = requests.post(search_url, data=json.dumps(self.query)).json()
        scroll_id = response['_scroll_id']
        l = response['hits']['total']

        while l > 0:
            response = requests.post(scroll_url, data=scroll_id).json()
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg = 'Elasticsearch failed to retrieve documents: ' \
                      '*** Shards: {0} *** Timeout: {1} *** Took: {2}'.format(response['_shards'], response['timed_out'], response['took'])
                raise esIteratorError(msg)

            for hit in response['hits']['hits']:
                sentences = hit['_source'][self.field].split('\n')
                reduction_methods = self.request.POST.getlist('lexicon_reduction[]')
                if u'remove_numbers' in reduction_methods:
                    # remove numbers
                    sentences = [re.sub('(\d)+','n',sentence) for sentence in sentences]
                if u'remove_punctuation' in reduction_methods:
                    # remove punctuation
                    sentences = [self.punct_re.sub('[punct]',sentence) for sentence in sentences]
                for sentence in sentences:
                    yield [smart_str(word.strip().lower()) for word in sentence.split(' ')]

            if self.callback_progress:
                self.callback_progress.update(l)

    def get_total_documents(self):
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=100'.format(es_url, self.dataset, self.mapping)
        data = json.dumps(self.query)
        response = requests.post(search_url, data=data).json()
        total = response['hits']['total']
        return long(total)
