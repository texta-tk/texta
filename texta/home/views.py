# -*- coding:utf-8 -*-
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
import requests

from ..model_manager.models import ModelRun
from .. utils.datasets import Datasets
from ..utils.es_manager import ES_Manager
from ..utils.log_manager import LogManager

from settings import STATIC_URL, es_url, URL_PREFIX


def autocomplete_data(request):
    logger = LogManager(__name__, 'AUTOCOMPLETE')

    session = request.session
    datasets = Datasets().activate_dataset(session)

    es_index = datasets.get_index()
    mapping = datasets.get_mapping()
    date_range = datasets.get_date_range()

    es_m = ES_Manager(es_index, mapping, date_range)
    fields = es_m.get_mapped_fields()

    # TODO: move to ES Manager
    # Get term aggregations for fields (for autocomplete)
    unique_limit = 10
    query = {"aggs":{}}
    field_values = {}
    for field in fields:
        if field['type'] == 'string':
            query["aggs"][field['path']] = {"terms": {"field": field['path'], "size": unique_limit+1}}

    response = requests.post(es_url+'/'+es_index+'/'+mapping+'/_search', data=json.dumps(query)).json()

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


def index(request):
    template = loader.get_template('home/home_index.html')
    ds = Datasets().activate_dataset(request.session)
    datasets = ds.get_datasets()

    #if ds.is_active():
    #    es_m = ds.build_manager(ES_Manager)
    #    autocomplete_dict = dict()
    #    autocomplete_dict['TEXT'] = autocomplete_data(request)
    #    autocomplete_dict['FACT'] = get_facts_autocomplete(es_m)
    #    request.session['autocomplete_data'] = autocomplete_dict

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
