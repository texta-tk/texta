#-*- coding:utf-8 -*-
import json
import logging
import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from model_manager.models import ModelRun
from settings import STATIC_URL, es_url, URL_PREFIX, INFO_LOGGER

from utils.datasets import get_datasets,get_active_dataset
from utils.es_manager import ES_Manager


def autocomplete_data(request, datasets):
    # Define selected mapping
    dataset, mapping, date_range = get_active_dataset(request.session['dataset'])

    es_m = ES_Manager(dataset, mapping, date_range)
    fields = es_m.get_mapped_fields()

    # TODO: move to ES Manager
    # Get term aggregations for fields (for autocomplete)
    unique_limit = 10
    query = {"aggs":{}}
    field_values = {}
    for field in fields:
        if field['type'] == 'string':
            query["aggs"][field['path']] = {"terms": {"field": field['path'], "size": unique_limit+1}}

    response = requests.post(es_url+'/'+dataset+'/'+mapping+'/_search', data=json.dumps(query)).json()

    for a in response["aggregations"].items():
        terms = [b["key"] for b in a[1]["buckets"]]
        if len(terms) <= unique_limit:
            field_values[a[0]] = terms

    return field_values


def get_facts_autocomplete(es_m):
    facts_structure = es_m.get_facts_structure()
    # invert facts_structure to have {field: [list of facts]}
    inverted_facts_structure = {}
    for k, v in facts_structure.items():
        for field in v:
            if field not in inverted_facts_structure:
                inverted_facts_structure[field] = []
            inverted_facts_structure[field].append(k)
    return inverted_facts_structure


def index(request):
    datasets = get_datasets()
    template = loader.get_template('home/home_index.html')
    try:
        request.session['dataset']
    except KeyError:
        try:
            request.session['dataset'] = datasets.keys()[0]
            # Define selected mapping
            dataset, mapping, date_range = get_active_dataset(request.session['dataset'])
            es_m = ES_Manager(dataset, mapping, date_range)
            autocomplete_dict = dict()
            autocomplete_dict['TEXT'] = autocomplete_data(request, datasets)
            autocomplete_dict['FACT'] = get_facts_autocomplete(es_m)
            request.session['autocomplete_data'] = autocomplete_dict
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

    dataset, mapping, date_range = get_active_dataset(request.session['dataset'])
    es_m = ES_Manager(dataset, mapping, date_range)

    # TODO: code refactoring

    try:
        if request.POST['model']:
            request.session['model'] = str(request.POST['model'])
            #logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CHANGE_SETTINGS','event':'model_updated','args':{'user_name':request.user.username,'new_model':request.POST['model']}}))
    except KeyError as e:
        print 'Exception: ', e
        # TODO shall not pass...

    try:
        if request.POST['dataset']:
            datasets = get_datasets()
            request.session['dataset'] = request.POST['dataset']
            autocomplete_dict = dict()
            autocomplete_dict['TEXT'] = autocomplete_data(request, datasets)
            autocomplete_dict['FACT'] = get_facts_autocomplete(es_m)
            request.session['autocomplete_data'] = autocomplete_dict
            #logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CHANGE_SETTINGS','event':'dataset_updated','args':{'user_name':request.user.username,'new_dataset':request.POST['mapping']}}))
    except KeyError as e:
        print 'Exception: ', e
        # TODO shall not pass...

    return HttpResponseRedirect(URL_PREFIX + '/')
