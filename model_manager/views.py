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
    threading.Thread(target=train_model,args=(search_id,field,num_dimensions,num_workers,min_freq,request.user,description,request)).start()
    return HttpResponse()

def train_model(search_id,field,num_dimensions,num_workers,min_freq,usr,description,request):
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
    sentences = esIterator(query,field,request)
    model = word2vec.Word2Vec(sentences,min_count=min_freq,size=num_dimensions,workers=num_workers)
    model.save(os.path.join(MODELS_DIR,'model_'+str(new_run.pk)))

    #lm_model_manager.add_model(str(new_run.pk),model)

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE MODEL','event':'model_training_completed','args':{'user_name':request.user.username},'data':{'run_id':new_run.id}}))

    # declare the job done
    r = ModelRun.objects.get(pk=new_run.pk)
    r.run_completed = datetime.now()
    r.run_status = 'completed'
    r.lexicon_size = len(model.vocab)
    r.save()
    print 'job is done'

class esIterator(object):
    def __init__(self,query,field,request):
        self.query = query
        self.field = field
        self.request = request
        self.punct_re = re.compile('[%s]' % re.escape(string.punctuation))

        # Define selected mapping
        self.datasets = get_datasets()
        self.selected_mapping = int(request.session['dataset'])
        self.dataset = self.datasets[self.selected_mapping]['index']
        self.mapping = self.datasets[self.selected_mapping]['mapping']

    def __iter__(self):
        response = requests.post(es_url+'/'+self.dataset+'/'+self.mapping+'/_search?search_type=scan&scroll=1m&size=1000',data=json.dumps(self.query)).json()
        scroll_id = response['_scroll_id']
        l = response['hits']['total']
        while l > 0:
            response = requests.post(es_url+'/_search/scroll?scroll=1m',data=scroll_id).json()
            l = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
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
