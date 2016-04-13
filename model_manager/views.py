# -*- coding: utf8 -*-
import json
import logging
import os
import string
import threading
from datetime import datetime

import nltk
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
from settings import STATIC_URL, es_url, URL_PREFIX, MODELS_DIR, INFO_LOGGER

from utils.datasets import get_datasets

@login_required
@permission_required('model_manager.change_modelrun')
def index(request):    
    # Define selected mapping
    datasets = get_datasets()
    selected_mapping = int(request.session['dataset'])
    dataset = datasets[selected_mapping]['index']
    mapping = datasets[selected_mapping]['mapping']
    template = loader.get_template('model_manager/model_manager_index.html')
    return HttpResponse(template.render({'searches':Search.objects.filter(author=request.user,dataset=Dataset(pk=selected_mapping)),'STATIC_URL':STATIC_URL,'runs':ModelRun.objects.all().order_by('-pk'),'fields':requests.get(es_url+'/'+dataset).json()[dataset]['mappings'][mapping]['properties']},request))

@login_required
@permission_required('model_manager.change_modelrun')
def delete_model(request):
    model_id = request.GET['model_id']
    run = ModelRun.objects.get(pk=model_id)
    if run.user == request.user:
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
    reduction_methods = request.POST.getlist('lexicon_reduction[]')
    threading.Thread(target= train_model,
                     args= (search_id, field, num_dimensions, num_workers, min_freq, request.user, description, request, reduction_methods)).start()
    return HttpResponse()


def train_model(search_id, field, num_dimensions, num_workers, min_freq, usr, description, request, reduction_methods):
    # add Run to db
    dataset_pk = int(request.session['dataset'])
    new_run = ModelRun(run_description=description,
                       min_freq=min_freq,
                       num_dimensions=num_dimensions,
                       num_workers=num_workers,
                       fields=field,
                       search=Search.objects.get(pk=search_id).query,run_status='running',
                       run_started=datetime.now(),run_completed=None,user=usr)
    new_run.save()
    
    logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE MODEL','event':'model_training_started','args':{'user_name':request.user.username,'search_id':search_id,'field':field,'num_dimensions':num_dimensions,'num_workers':num_workers,'min_freq':min_freq,'desc':description},'data':{'run_id':new_run.id}}))
    
    print 'Run added to db.'
    query = json.loads(Search.objects.get(pk=search_id).query)

    num_passes = 5
    # Number of word2vec passes + one pass to vocabulary building
    total_passes = num_passes + 1
    show_progress = ShowProgress(new_run.pk, multiplier=total_passes)
    show_progress.update_view(0)

    sentences = esIterator(query, field, request, reduction_methods, callback_progress=show_progress)

    model = word2vec.Word2Vec(sentences, min_count = min_freq,
                                         size = num_dimensions,
                                         workers = num_workers,
                                         iter = num_passes)

    model_name = 'model_'+str(new_run.pk)
    output_model_file = os.path.join(MODELS_DIR, model_name)
    model.save(output_model_file)

    #lm_model_manager.add_model(str(new_run.pk), model)

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE MODEL','event':'model_training_completed','args':{'user_name':request.user.username},'data':{'run_id':new_run.id}}))

    # declare the job done
    r = ModelRun.objects.get(pk=new_run.pk)
    r.run_completed = datetime.now()
    r.run_status = 'completed'
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
        print('--- progress: {0:3.0f} %'.format(percentage))
        r = ModelRun.objects.get(pk=self.model_pk)
        r.run_status = 'running [{0:3.0f} %]'.format(percentage)
        r.save()


class esIterator(object):
    """  ElasticSearch Iterator
    """

    MIN_SENTENCE_LENGTH = 2
    PUNCTUATION_TOKEN = ' [punct] '
    NUMBER_TOKEN = ' [number] '

    def __init__(self, query, field, request, reduction_methods, callback_progress = None):
        self.query = query
        self.field = field
        self.request = request
        # Define selected mapping
        self.datasets = get_datasets()
        self.selected_mapping = int(request.session['dataset'])
        self.dataset = self.datasets[self.selected_mapping]['index']
        self.mapping = self.datasets[self.selected_mapping]['mapping']
        self.reduction_methods = reduction_methods
        self.callback_progress = callback_progress

        if self.callback_progress:
            total_elements = self.get_total_documents()
            callback_progress.set_total(total_elements)

    def __iter__(self):
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=1000'.format(es_url, self.dataset, self.mapping)
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(es_url)
        data = json.dumps(self.query)
        response = requests.post(search_url, data = data).json()
        scroll_id = response['_scroll_id']
        l = response['hits']['total']

        while l > 0:
            response = requests.post(scroll_url,data = scroll_id).json()
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']

            for hit in response['hits']['hits']:
                document = hit['_source'][self.field]
                # Divide the document hit into sentences
                sentences = nltk.sent_tokenize(document)
                for sentence in sentences:
                    # Apply transformations to the sentence
                    sentence = self.transform_sentence(sentence)
                    # Divide every sentence into words
                    words = nltk.word_tokenize(sentence)
                    # If sentence is too short, continue
                    if len(words) <= self.MIN_SENTENCE_LENGTH:
                        continue
                    words = [self.transform_word(w) for w in words]
                    yield words
            if self.callback_progress:
                self.callback_progress.update(l)

    def get_total_documents(self):
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=1000'.format(es_url, self.dataset, self.mapping)
        data = json.dumps(self.query)
        response = requests.post(search_url, data = data).json()
        total = response['hits']['total']
        return long(total)

    def transform_sentence(self, sentence):
        """ Applies string transformations and reduction methods to the input sentence
            Returns: the transformed sentence string
        """
        all_punct = string.punctuation
        all_punct += '\xc2\xab\xc2\xbb\xc2\xba'.decode('utf-8')
        for c in all_punct:
            new_c = self.PUNCTUATION_TOKEN if u'remove_punctuation' in self.reduction_methods else u' {0} '.format(c)
            sentence = sentence.replace(c, new_c)
        return sentence

    def transform_word(self, w):
        """ Applies string transformations and reduction methods to the input word w
            Returns: the transformed word string
        """
        if u'remove_punctuation' in self.reduction_methods:
            # remove punctuation
            w = self.PUNCTUATION_TOKEN if w in string.punctuation else w
        if u'remove_numbers' in self.reduction_methods:
            # remove numbers
            w = self.NUMBER_TOKEN if self.is_number(w) else w

        w = w.strip().lower()
        w = smart_str(w)
        return w

    @staticmethod
    def is_number(s):
        """ Checks if input string s is a valid number
            Returns: True if the string can be converted to a float number, False otherwise
        """
        try:
            float(s)
            return True
        except ValueError:
            pass
        return False