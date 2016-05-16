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


def _check_if_has_facts(es_url, _index, _type, sub_fields):
    """ Check if field is associate with facts in Elasticsearch
    """
    doc_type = _type.lower()
    field_path = [s.lower() for s in sub_fields]
    doc_path = '.'.join(field_path)
    request_url = '{0}/{1}/{2}/_count'.format(es_url, _index, 'texta')
    q = {"query": { "bool": { "filter": {'and': []}}}}
    q['query']['bool']['filter']['and'].append({ "term": {'facts.doc_type': doc_type }})
    q['query']['bool']['filter']['and'].append({ "term": {'facts.doc_path': doc_path }})
    q = json.dumps(q)
    response = requests.post(request_url, data=q).json()
    return response['count'] > 0


def _decode_mapping_structure(structure, root_path=list()):
    """ Decode mapping structure (nested dictionary) to a flat structure
    """
    mapping_data = []

    for item in structure.items():
        if 'properties' in item[1]:
            sub_structure = item[1]['properties']
            path_list = root_path[:]
            path_list.append(item[0])
            sub_mapping = _decode_mapping_structure(sub_structure, root_path=path_list)
            mapping_data.extend(sub_mapping)
        else:
            path_list = root_path[:]
            path_list.append(item[0])
            path = '.'.join(path_list)
            data = {'path': path, 'type': item[1]['type']}
            mapping_data.append(data)

    return mapping_data


def get_mapped_fields(es_url, dataset, mapping):
    """ Get flat structure of fields from Elasticsearch mapping
    """
    mapping_structure = requests.get(es_url+'/'+dataset).json()[dataset]['mappings'][mapping]['properties']
    mapping_data = _decode_mapping_structure(mapping_structure)
    return mapping_data


def autocomplete_data(request, datasets):
    # Define selected mapping
    dataset, mapping, _ = get_active_dataset(request.session['dataset'])

    fields = get_mapped_fields(es_url, dataset, mapping)
    fields = sorted(fields, key=lambda l: l['path'])

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


def index(request):
    datasets = get_datasets()
    template = loader.get_template('home/home_index.html')
    try:
        request.session['dataset']
    except KeyError:
        try:
            request.session['dataset'] = datasets.keys()[0]
            autocomplete_dict = dict()
            autocomplete_dict['TEXT'] = autocomplete_data(request,datasets)
            autocomplete_dict['FACT'] = {'document.text': ['doc_order']}
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
            autocomplete_dict['FACT'] = {'document.text': ['doc_order']}
            request.session['autocomplete_data'] = autocomplete_dict
            #logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CHANGE_SETTINGS','event':'dataset_updated','args':{'user_name':request.user.username,'new_dataset':request.POST['mapping']}}))
    except KeyError as e:
        print 'Exception: ', e
        # TODO shall not pass...

    return HttpResponseRedirect(URL_PREFIX + '/')
