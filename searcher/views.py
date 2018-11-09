# -*- coding: utf8 -*-
from __future__ import print_function
from __future__ import absolute_import
import calendar
import logging

import platform
if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process


import json
import csv
import re
from datetime import datetime, timedelta as td
try:
    from io import BytesIO # NEW PY REQUIREMENT
except:
    from io import StringIO # NEW PY REQUIREMENT

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.template import loader
from django.utils.encoding import smart_str
# For string templates
from django.template import Context
from django.template import Template

from texta.settings import STATIC_URL, URL_PREFIX, date_format, es_links, INFO_LOGGER, ERROR_LOGGER

from dataset_importer.document_preprocessor.preprocessor import DocumentPreprocessor, preprocessor_map
from conceptualiser.models import Term, TermConcept
from permission_admin.models import Dataset
from lexicon_miner.models import Lexicon,Word
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from utils.highlighter import Highlighter, ColorPicker
from utils.autocomplete import Autocomplete
from dataset_importer.document_preprocessor import preprocessor_map

from task_manager.views import task_params
from task_manager.models import Task

from searcher.models import Search
from searcher.view_functions.aggregations.agg_manager import AggManager
from searcher.view_functions.build_search.build_search import execute_search
from searcher.view_functions.cluster_search.cluster_manager import ClusterManager
from searcher.view_functions.general.fact_manager import FactManager
from searcher.view_functions.general.get_saved_searches import extract_constraints
from searcher.view_functions.general.export_pages import export_pages
from searcher.view_functions.general.searcher_utils import collect_map_entries, get_fields_content, get_fields


@login_required
def index(request):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)

    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type='train_model').filter(status__iexact='completed').order_by('-pk')

    preprocessors = collect_map_entries(preprocessor_map)
    enabled_preprocessors = [preprocessor for preprocessor in preprocessors]

    # Hide fact graph if no facts_str_val is present in fields
    display_fact_graph = 'hidden'
    for i in fields:
        if json.loads(i['data'])['type'] == "fact_str_val":
            display_fact_graph = ''
            break

    template_params = {'display_fact_graph': display_fact_graph,
                       'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'searches': Search.objects.filter(author=request.user),
                       'lexicons': Lexicon.objects.all().filter(author=request.user),
                       'language_models': language_models, 
                       'allowed_datasets': datasets,                       
                       'enabled_preprocessors': enabled_preprocessors,
                       'task_params': task_params}

    template = loader.get_template('searcher.html')

    return HttpResponse(template.render(template_params, request))


@login_required
def get_query(request):
    es_params = request.POST
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    # GET ONLY MAIN QUERY
    query = es_m.combined_query['main']
    return HttpResponse(json.dumps(query))


@login_required
def save(request):
    logger = LogManager(__name__, 'SAVE SEARCH')

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)

    es_params = request.POST
    es_m.build(es_params)
    combined_query = es_m.get_combined_query()

    try:
        q = combined_query
        desc = request.POST['search_description']
        s_content = json.dumps([request.POST[x] for x in request.POST.keys() if 'match_txt' in x])



        search = Search(author=request.user, search_content=s_content, description=desc, query=json.dumps(q))
        search.save()

        for dataset_id in request.session['dataset']:
            dataset = Dataset.objects.get(pk=int(dataset_id))
            search.datasets.add(dataset)

        search.save()

        logger.set_context('user_name', request.user.username)
        logger.set_context('search_id', search.id)
        logger.info('search_saved')

    except Exception as e:
        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.set_context('es_params', es_params)
        logger.exception('search_saving_failed')

    return HttpResponse()


@login_required
def delete(request):
    logger = LogManager(__name__, 'DELETE SEARCH')
    search_id = request.GET['pk']
    logger.set_context('user_name', request.user.username)
    logger.set_context('search_id', search_id)
    try:
        Search.objects.get(pk=search_id).delete()
        logger.info('search_deleted')

    except Exception as e:
        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.exception('search_deletion_failed')

    return HttpResponse(search_id)


@login_required
def autocomplete(request):
    ac = Autocomplete()
    ac.parse_request(request)
    suggestions = ac.suggest()
    suggestions = json.dumps(suggestions)

    return HttpResponse(suggestions)


@login_required
def get_saved_searches(request):
    active_dataset_ids = [int(ds) for ds in request.session['dataset']]
    active_datasets = Dataset.objects.filter(pk__in=active_dataset_ids)
    searches = Search.objects.filter(author=request.user).filter(datasets__in=active_datasets).distinct()
    return HttpResponse(json.dumps([{'id':search.pk,'desc':search.description} for search in searches],ensure_ascii=False))


@login_required
def get_table_header(request):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)

    # get columns names from ES mapping
    fields = es_m.get_column_names()
    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'searches': Search.objects.filter(author=request.user),
                       'columns': [{'index':index, 'name':field_name} for index, field_name in enumerate(fields)],
                       }
    template = loader.get_template('searcher_results.html')
    return HttpResponse(template.render(template_params, request))


@login_required
def get_table_content(request):
    request_param = request.POST
    echo = int(request_param['sEcho'])
    filter_params = json.loads(request_param['filterParams'])
    es_params = {filter_param['name']: filter_param['value'] for filter_param in filter_params}
    es_params['examples_start'] = request_param['iDisplayStart']
    es_params['num_examples'] = request_param['iDisplayLength']
    result = search(es_params, request)
    result['sEcho'] = echo

    # NEW PY REQUIREMENT
    # Get rid of 'odict_values' otherwise can't json dumps
    for i in range(len(result['aaData'])):
        result['aaData'][i] = list(result['aaData'][i])

    return HttpResponse(json.dumps(result, ensure_ascii=False))


@login_required
def mlt_query(request):
    es_params = request.POST

    mlt_fields = [json.loads(field)['path'] for field in es_params.getlist('mlt_fields')]

    handle_negatives = request.POST['handle_negatives']
    docs_accepted = [a.strip() for a in request.POST['docs'].split('\n') if a]
    docs_rejected = [a.strip() for a in request.POST['docs_rejected'].split('\n') if a]

    # stopwords
    stopword_lexicon_ids = request.POST.getlist('mlt_stopword_lexicons')
    stopwords = []

    for lexicon_id in stopword_lexicon_ids:
        lexicon = Lexicon.objects.get(id=int(lexicon_id))
        words = Word.objects.filter(lexicon=lexicon)
        stopwords+=[word.wrd for word in words]

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    response = es_m.more_like_this_search(mlt_fields,docs_accepted=docs_accepted,docs_rejected=docs_rejected,handle_negatives=handle_negatives,stopwords=stopwords)

    documents = []
    for hit in response['hits']['hits']:
        fields_content = get_fields_content(hit,mlt_fields)
        documents.append({'id':hit['_id'],'content':fields_content})

    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'documents':documents}
    template = loader.get_template('mlt_results.html')
    return HttpResponse(template.render(template_params, request))


@login_required
def cluster_query(request):
    params = request.POST
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(params)

    cluster_m = ClusterManager(es_m,params)
    clustering_data = cluster_m.convert_clustering_data()

    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'clusters': clustering_data}

    template = loader.get_template('cluster_results.html')
    return HttpResponse(template.render(template_params, request))


def search(es_params, request):
    logger = LogManager(__name__, 'SEARCH CORPUS')

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    try:
        out = execute_search(es_m, es_params)
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process': 'SEARCH DOCUMENTS', 'event': 'documents_queried_failed'}), exc_info=True)
        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.set_context('user_name', request.user.username)
        logger.error('documents_queried_failed')

        out = {'column_names': [], 'aaData': [], 'iTotalRecords': 0, 'iTotalDisplayRecords': 0, 'lag': 0}

    logger.set_context('query', es_m.get_combined_query())
    logger.set_context('user_name', request.user.username)
    logger.info('documents_queried')
    return out


@login_required
def remove_by_query(request):
    es_params = request.POST

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    #Process(target=remove_worker,args=(es_m,'notimetothink')).start()
    response = remove_worker(es_m, 'notimetothink')
    return HttpResponse(response)


def remove_worker(es_m, dummy):
    '''Function for remove_by_query multiprocessing'''
    response = es_m.delete()
    return response
    # TODO: add logging


@login_required
def aggregate(request):
    agg_m = AggManager(request)
    data = agg_m.output_to_searcher()
    return HttpResponse(json.dumps(data))


@login_required
def delete_facts(request):
    fact_m = FactManager(request)
    #Process(target=fact_m.remove_facts_from_document, args=(dict(request.POST),)).start()
    fact_m.remove_facts_from_document(request.POST)

    return HttpResponse()


@login_required
def tag_documents(request):
    """Add a fact to documents with given name and value
       via Search > Actions > Tag results
    """
    tag_name = request.POST['tag_name']
    tag_value = request.POST['tag_value']
    tag_field = request.POST['tag_field']
    es_params = request.POST

    fact_m = FactManager(request)
    fact_m.tag_documents_with_fact(es_params, tag_name, tag_value, tag_field)
    return HttpResponse()


@login_required
def get_search_query(request):
    search_id = request.GET.get('search_id', None)

    if search_id == None:
        return HttpResponse(status=400)

    search = Search.objects.get(pk=search_id)

    if not search:
        return HttpResponse(status=404)

    query = json.loads(search.query)
    query_constraints = extract_constraints(query)
	# For original search content such as unpacked lexicons/concepts
    search_content = json.loads(search.search_content)

    for i in range(len([x for x in query_constraints if x['constraint_type'] == 'string'])):
        query_constraints[i]['content'] = [search_content[i]]

    return HttpResponse(json.dumps(query_constraints))


@login_required
def fact_graph(request):

    search_size = int(request.POST['fact_graph_size'])

    fact_m = FactManager(request)
    try:
        graph_data, fact_names, max_node_size, max_link_size, min_node_size = fact_m.fact_graph(search_size)

        template_params = {'STATIC_URL': STATIC_URL,
                        'URL_PREFIX': URL_PREFIX,
                        'search_id': 1,
                        'searches': Search.objects.filter(author=request.user),
                        'graph_data': graph_data,
                        'max_node_size': max_node_size,
                        'max_link_size': max_link_size,
                        'min_node_size': min_node_size,
                        'fact_names': fact_names}
        template = loader.get_template('fact_graph_results.html')
    except Exception as e:
        template = Template('An error has occurred in <i>{{func}}</i>: <i>{{error}}</i>')
        template_params = Context({'func':'fact graph', 'error': str(e)})
        return HttpResponse(template.render(template_params))

    return HttpResponse(template.render(template_params, request))
