# -*- coding: utf8 -*-
from __future__ import print_function
from __future__ import absolute_import
import calendar
import logging

import platform
from pprint import pprint

if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process

import json
import csv
import re
from datetime import datetime, timedelta as td

try:
    from io import BytesIO  # NEW PY REQUIREMENT
except:
    from io import StringIO  # NEW PY REQUIREMENT

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse, HttpResponseBadRequest, JsonResponse
from django.template import loader
from django.utils.encoding import smart_str
from searcher.dashboard.dashboard import SingleSearcherDashboard, MultiSearcherDashboard
# For string templates
from django.template import Context
from django.template import Template
import collections
from texta.settings import STATIC_URL, URL_PREFIX, date_format, es_links, INFO_LOGGER, ERROR_LOGGER, es_url

from dataset_importer.document_preprocessor.preprocessor import preprocessor_map
from conceptualiser.models import Term, TermConcept
from permission_admin.models import Dataset
from lexicon_miner.models import Lexicon, Word
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from utils.highlighter import Highlighter, ColorPicker
from utils.autocomplete import Autocomplete

from task_manager.models import Task

from texta.settings import STATIC_URL, URL_PREFIX, date_format, es_links, INFO_LOGGER, ERROR_LOGGER, es_url

try:
    from io import BytesIO  # NEW PY REQUIREMENT
except:
    from io import StringIO  # NEW PY REQUIREMENT

from searcher.models import Search
from searcher.view_functions.aggregations.agg_manager import AggManager
from searcher.view_functions.build_search.build_search import execute_search
from searcher.view_functions.cluster_search.cluster_manager import ClusterManager
from searcher.view_functions.general.fact_manager import FactManager
from searcher.view_functions.general.fact_manager import FactAdder
from searcher.view_functions.general.fact_manager import FactGraph
from searcher.view_functions.general.get_saved_searches import extract_constraints
from searcher.view_functions.general.export_pages import export_pages
from searcher.view_functions.general.searcher_utils import collect_map_entries, get_fields_content, get_fields
from collections import OrderedDict, defaultdict
from searcher.view_functions.general.searcher_utils import improve_facts_readability


class BuildSearchEsManager:
    build_search_es_m = None


def ngrams(input_list, n):
    return zip(*[input_list[i:] for i in range(n)])


def convert_date(date_string, frmt):
    return datetime.strptime(date_string, frmt).date()


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        value['key'] = key
        entries.append(value)

    return entries


def get_fields(es_m):
    texta_reserved = ['texta_facts']
    mapped_fields = es_m.get_mapped_fields()
    fields_with_facts = es_m.get_fields_with_facts()

    fields = []

    for mapped_field, dataset_info in mapped_fields.items():
        data = json.loads(mapped_field)

        path = data['path']

        if path not in texta_reserved:

            path_list = path.split('.')

            label = '{0} --> {1}'.format(path_list[0], path_list[-1]) if len(path_list) > 1 else path_list[0]
            label = label.replace('-->', u'→')

            if data['type'] == 'date':
                data['range'] = get_daterange(es_m, path)

            data['label'] = label

            field = {'data': json.dumps(data), 'label': label, 'type': data['type']}
            fields.append(field)

            if path in fields_with_facts['fact']:
                data['type'] = 'facts'
                field = {'data': json.dumps(data), 'label': label + ' [fact_names]', 'type': 'facts'}
                fields.append(field)

            if path in fields_with_facts['fact_str']:
                data['type'] = 'fact_str_val'
                field = {'data': json.dumps(data), 'label': label + ' [fact_text_values]', 'type': 'facts'}
                fields.append(field)

            if path in fields_with_facts['fact_num']:
                data['type'] = 'fact_num_val'
                field = {'data': json.dumps(data), 'label': label + ' [fact_num_values]', 'type': 'facts'}
                fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])

    return fields


def get_daterange(es_m, field):
    min_val, max_val = es_m.get_extreme_dates(field)
    return {'min': min_val, 'max': max_val}


def dashboard_endpoint(request):
    es_params = request.POST
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    query_dict = es_m.combined_query['main']  # GET ONLY MAIN QUERY
    print(query_dict)

    indices = request.POST.get("chosen_index", None)

    dashboard = MultiSearcherDashboard(es_url=es_url, indices=indices, query_body=query_dict)

    query_result = dashboard.conduct_query()
    formated_result = dashboard.format_result(query_result)

    return JsonResponse(formated_result)


@login_required
def dashboard_visualize(request):
    es_params = request.POST

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    indices = es_params.get("chosen_index", None).split(',')

    color_setting = request.POST['dashboard-color']
    color_max = request.POST['dashboard-color-maximum']
    color_min = request.POST['dashboard-color-minimum']
    template = loader.get_template('dashboard/dashboard.html')

    return HttpResponse(template.render({'STATIC_URL': STATIC_URL,
                                         'color_setting': color_setting,
                                         'color_max': color_max,
                                         'color_min': color_min,
                                         'URL_PREFIX': URL_PREFIX,
                                         'indices': indices}, request))


@login_required
def index(request):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    fields = get_fields(es_m)

    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type='train_model').filter(status__iexact='completed').order_by('-pk')

    preprocessors = collect_map_entries(preprocessor_map)
    enabled_preprocessors = [preprocessor for preprocessor in preprocessors if preprocessor['is_enabled'] is True]

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
                       'enabled_preprocessors': enabled_preprocessors}

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
        s_content = {}

        # make json
        for x in request.POST.keys():
            if 'match_txt' in x:
                # get the ID of the field, eg match_txt_1 returns 1 match_txt_1533 returns 1533
                field_id = x.rsplit("_", 1)[-1]
                match_field = request.POST['match_field_' + field_id]
                if match_field in s_content.keys():
                    s_content[match_field].append(request.POST[x])
                else:
                    s_content[match_field] = [request.POST[x]]

        search = Search(author=request.user, search_content=json.dumps(s_content), description=desc,
                        query=json.dumps(q))
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
    post_data = json.loads(request.POST['data'])
    logger = LogManager(__name__, 'DELETE SEARCH')
    search_ids = post_data['pks']
    logger.set_context('user_name', request.user.username)
    logger.set_context('search_ids', search_ids)
    try:
        for search_id in search_ids:
            Search.objects.get(pk=search_id).delete()
            logger.info('search_deleted:' + search_id)

    except Exception as e:
        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.exception('search_deletion_failed')

    return HttpResponse()


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
    return HttpResponse(
        json.dumps([{'id': search.pk, 'desc': search.description} for search in searches], ensure_ascii=False))


@login_required
def get_table_header(request):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)

    # get columns names from ES mapping
    fields = es_m.get_column_names(facts=True)
    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'searches': Search.objects.filter(author=request.user),
                       'columns': [{'index': index, 'name': field_name} for index, field_name in enumerate(fields)],
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

    return HttpResponse(json.dumps(result, ensure_ascii=False))


@login_required
def table_header_mlt(request):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)

    # get columns names from ES mapping
    fields = es_m.get_column_names(facts=True)
    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'searches': Search.objects.filter(author=request.user),
                       'columns': [{'index': index, 'name': field_name} for index, field_name in enumerate(fields)],
                       }
    template = loader.get_template('mlt_results.html')
    return HttpResponse(template.render(template_params, request))


@login_required
def mlt_query(request):
    es_params = request.POST

    if 'mlt_fields' not in es_params:
        return HttpResponse(status=400, reason='field')
    else:
        if es_params['mlt_fields'] == '[]':
            return HttpResponse(status=400, reason='field')
    if BuildSearchEsManager.build_search_es_m is None:
        return HttpResponse(status=400, reason='search')

    mlt_fields = [field for field in json.loads(es_params['mlt_fields'])]
    handle_negatives = es_params['handle_negatives']
    docs_accepted = [a.strip() for a in es_params['docs'].split('\n') if a]
    docs_rejected = [a.strip() for a in es_params['docs_rejected'].split('\n') if a]

    stopword_lexicon_ids = json.loads(es_params['mlt_stopword_lexicons'])
    stopwords = []
    for lexicon_id in stopword_lexicon_ids:
        lexicon = Lexicon.objects.get(id=int(lexicon_id))
        words = Word.objects.filter(lexicon=lexicon)
        stopwords += [word.wrd for word in words]

    search_size = es_params['search_size']
    draw = int(es_params['draw'])

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    es_m.set_query_parameter('from', es_params['start'])
    es_m.set_query_parameter('size', search_size)

    response = es_m.more_like_this_search(mlt_fields, docs_accepted=docs_accepted, docs_rejected=docs_rejected,
                                          handle_negatives=handle_negatives, stopwords=stopwords,
                                          search_size=search_size,
                                          build_search_query=BuildSearchEsManager.build_search_es_m.build_search_query)

    result = {'data': [], 'draw': draw, 'recordsTotal': len(response['hits']['hits'])}
    column_names = es_m.get_column_names(facts=True)

    for hit in response['hits']['hits']:
        hit_id = str(hit['_id'])
        hit['_source']['_es_id'] = hit_id
        row = OrderedDict([(x, '') for x in column_names])

        for col in column_names:
            # If the content is nested, need to break the flat name in a path list
            field_path = col.split('.')
            # Get content for the fields and make facts human readable
            for p in field_path:
                if col == u'texta_facts' and p in hit['_source']:
                    content = improve_facts_readability(hit['_source'][p])
                else:
                    content = hit['_source'][p] if p in hit['_source'] else ''

            # Append the final content of this col to the row
            if row[col] == '':
                row[col] = content

        result['data'].append([hit_id, hit_id] + list(row.values()))

    return HttpResponse(json.dumps(result, ensure_ascii=False))


@login_required
def cluster_query(request):
    params = request.POST
    if ('cluster_field' not in params):
        return HttpResponse(status=400, reason='field')
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(params)

    cluster_m = ClusterManager(es_m, params)
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
    BuildSearchEsManager.build_search_es_m = es_m
    try:
        out = execute_search(es_m, es_params)
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(
            json.dumps({'process': 'SEARCH DOCUMENTS', 'event': 'documents_queried_failed'}), exc_info=True)
        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.set_context('user_name', request.user.username)
        logger.error('documents_queried_failed')

        out = {'column_names': [], 'aaData': [], 'iTotalRecords': 0, 'iTotalDisplayRecords': 0, 'lag': 0}

    logger.set_context('query', es_m.get_combined_query())
    logger.set_context('user_name', request.user.username)
    logger.info('documents_queried')
    return out


def delete_document(request):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(request.POST)

    active_indices = es_m.stringify_datasets()
    doc_ids = request.POST.getlist('document_id[]')

    url = 'http://localhost:9200/' + active_indices + '/_delete_by_query?refresh=true'
    response = es_m.plain_post(url, data=json.dumps(
        {
            "query": {
                "ids": {
                    "values": doc_ids
                }
            }
        }
    ))
    return HttpResponse(json.dumps(response))


@login_required
def remove_by_query(request):
    es_params = request.POST

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    # Process(target=remove_worker,args=(es_m,'notimetothink')).start()
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
    # Process(target=fact_m.remove_facts_from_document, args=(dict(request.POST),)).start()
    params = dict(request.POST)
    if 'doc_id' in params:
        doc_id = params.pop('doc_id')[0]
    else:
        doc_id = False
    fact_m.remove_facts_from_document(params, doc_id)
    return HttpResponse()


@login_required
def fact_to_doc(request):
    """Add a fact to a certain document with given fact, span, and the document _id"""
    fact_name = request.POST['fact_name'].strip()
    fact_value = request.POST['fact_value'].strip()
    fact_field = request.POST['fact_field'].strip()
    method = request.POST['method'].strip()
    match_type = request.POST['match_type'].strip()
    doc_id = request.POST['doc_id'].strip()
    case_sens = True if request.POST['case_sens'].strip() == "True" else False
    es_params = request.POST

    # Validate that params aren't empty strings
    if len(fact_name) > 0 and len(fact_value) > 0 and len(fact_field) > 0 and len(doc_id) > 0 and len(method) > 0:
        fact_a = FactAdder(request, es_params, fact_name, fact_value, fact_field, doc_id, method, match_type, case_sens)
        json_response = fact_a.add_facts()
    else:
        return HttpResponseBadRequest()
    if json_response:
        return JsonResponse(json_response)
    else:
        return JsonResponse({'fact_count': 0, 'status': 'error'})


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
    search_content = json.loads(search.search_content)

    # For original search content such as unpacked lexicons/concepts
    matches = []

    for i in range(len(query_constraints)):
        if query_constraints[i]['constraint_type'] == 'string':
            field_text = query_constraints[i]['content']
            field_type = query_constraints[i]['field']
            not_present = True
            for x in search_content[field_type]:
                # strings match with query and text field match_txt
                if field_text[0] == x:
                    query_constraints[i]['content'] = [x]
                    search_content[field_type].remove(x)
                    not_present = False

            if not_present:
                matches.append(i)

    for k in matches:
        field_type = query_constraints[k]['field']
        for x in search_content[field_type]:
            # strings match with query and text field match_txt
            query_constraints[k]['content'] = [x]
            search_content[field_type].remove(x)

    return HttpResponse(json.dumps(query_constraints))


@login_required
def fact_graph(request):
    search_size = int(request.POST['fact_graph_size'])
    es_params = request.POST
    # fact_m = FactManager(request)
    fact_g = FactGraph(request, es_params, search_size)
    try:
        graph_data, fact_names, max_node_size, max_link_size, min_node_size = fact_g.fact_graph()

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
        template_params = Context({'func': 'fact graph', 'error': str(e)})
        return HttpResponse(template.render(template_params))

    return HttpResponse(template.render(template_params, request))
