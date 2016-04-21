#-*- coding:utf-8 -*-
import json
import logging
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from model_manager.models import ModelRun
from settings import STATIC_URL, es_url, URL_PREFIX, INFO_LOGGER
import time

from utils.datasets import get_datasets,get_active_dataset

def autocomplete_data(request,datasets):
    # Define selected mapping
    dataset,mapping,_ = get_active_dataset(request.session['dataset'])

    fields = [(a[0],a[1]['type']) for a in requests.get(es_url+'/'+index).json()[index]['mappings'][mapping]['properties'].items()]
    fields = sorted(fields,key=lambda l:l[0])

    # Get term aggregations for fields (for autocomplete)
    unique_limit = 10
    query = {"aggs":{}}
    field_values = {}
    for field in fields:
        if field[1] == 'string':
            query["aggs"][field[0]] = {"terms":{"field":field[0],"size":unique_limit+1}}
    response = requests.post(es_url+'/'+index+'/'+mapping+'/_search',data=json.dumps(query)).json()

    for a in response["aggregations"].items():
        terms = [b["key"] for b in a[1]["buckets"]]
        if len(terms) <= unique_limit:
            field_values[a[0]] = terms

    return field_values

def index(request):
    datasets = get_datasets()
    template = loader.get_template('home/home_index.html')
    try:
        request.session['dataset']
    except KeyError:
        try:
            request.session['dataset'] = datasets.keys()[0]
            request.session['autocomplete_data'] = autocomplete_data(request,datasets)
        except:
            IndexError

    # We should check if the model is actually present on the disk
    sem_models = ModelRun.objects.all().filter(run_status='completed').order_by('-pk')

    try:
        request.session['model']
    except KeyError:
        if len(sem_models):
            request.session['model'] = str(sem_models[0].id)

    return HttpResponse(template.render({'STATIC_URL':STATIC_URL, 'datasets':datasets,'models':sem_models},request))

@login_required
def update(request):
    try:
        if request.POST['model']:
            request.session['model'] = str(request.POST['model'])
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CHANGE_SETTINGS','event':'model_updated','args':{'user_name':request.user.username,'new_model':request.POST['model']}}))
    except KeyError as e:
        pass

    try:
        if request.POST['dataset']:
            datasets = get_datasets()
            request.session['dataset'] = request.POST['dataset']
            request.session['autocomplete_data'] = autocomplete_data(request,datasets)
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CHANGE_SETTINGS','event':'dataset_updated','args':{'user_name':request.user.username,'new_dataset':request.POST['mapping']}}))
    except KeyError as e:
        pass
    return HttpResponseRedirect(URL_PREFIX + '/')
