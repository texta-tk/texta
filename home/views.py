# -*- coding:utf-8 -*-
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
import requests

from model_manager.models import ModelRun
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager

from texta.settings import STATIC_URL, es_url, URL_PREFIX


def autocomplete_data(request):
    logger = LogManager(__name__, 'AUTOCOMPLETE')

    session = request.session
    datasets = Datasets().activate_dataset(session)

    es_index = datasets.get_index()
    mapping = datasets.get_mapping()

    es_m = ES_Manager(es_index, mapping)
    fields = es_m.get_mapped_fields()

    # TODO: move to ES Manager
    # Get term aggregations for fields (for autocomplete)
    unique_limit = 10
    query = {"aggs":{}}
    field_values = {}
    for field in fields:
        if field['type'] == 'string':
            query["aggs"][field['path']] = {"terms": {"field": field['path'], "size": unique_limit+1}}

    response = ES_Manager.plain_search(es_url, es_index, mapping, query)

    try:
        for a in response["aggregations"].items():
            terms = [b["key"] for b in a[1]["buckets"]]
            if len(terms) <= unique_limit:
                field_values[a[0]] = terms
    except KeyError:
        logger.exception('autocomplete_data')

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


def sort_datasets(datasets,indices):
    out = []

    open_indices = [index['index'] for index in indices if index['status'] == 'open']
    
    for dataset in sorted(datasets.items(),key=lambda l:l[1]['index']):
        ds = dataset[1]
        ds['id'] = dataset[0]
        if ds['index'] in open_indices:
            out.append(ds)
    return out

def get_allowed_datasets(datasets, user):
    return [dataset for dataset in datasets if user.has_perm('permission_admin.can_access_dataset_' + str(dataset['id']))]

def index(request):
    indices = ES_Manager.get_indices()
    
    template = loader.get_template('home.html')
    ds = Datasets().activate_dataset(request.session)
    datasets = sort_datasets(ds.get_datasets(),indices)
    datasets = get_allowed_datasets(datasets, request.user)

    # TODO: We should check if the model is actually present on the disk
    sem_models = ModelRun.objects.all().filter(run_status='completed').order_by('-pk')
    try:
        request.session['model']
    except KeyError:
        if len(sem_models):
            request.session['model'] = str(sem_models[0].id)

    return HttpResponse(template.render({'STATIC_URL':STATIC_URL, 'datasets':datasets,'models':sem_models},request))


@login_required
def update(request):
    logger = LogManager(__name__, 'CHANGE_SETTINGS')

    parameters = request.POST

    if 'model' in parameters:
        model = str(parameters['model'])
        request.session['model'] = model
        logger.clean_context()
        logger.set_context('user_name', request.user.username)
        logger.set_context('new_model', model)
        logger.info('dataset_updated')

    if 'dataset' in parameters:
        # TODO: check if is a valid mapping_id before change session[dataset]
        new_dataset = parameters['dataset']

        if request.user.has_perm('permission_admin.can_access_dataset_' + str(new_dataset)):
            request.session['dataset'] = new_dataset

            logger.clean_context()
            logger.set_context('user_name', request.user.username)
            logger.set_context('new_dataset', new_dataset)
            logger.info('dataset_updated')

            ds = Datasets().activate_dataset(request.session)
            es_m = ds.build_manager(ES_Manager)
            autocomplete_dict = dict()
            autocomplete_dict['TEXT'] = autocomplete_data(request)
            autocomplete_dict['FACT'] = get_facts_autocomplete(es_m)
            request.session['autocomplete_data'] = autocomplete_dict

    return HttpResponseRedirect(URL_PREFIX + '/')
