# -*- coding: utf8 -*-
from __future__ import print_function
from __future__ import absolute_import
import calendar
from collections import Counter
import logging

import platform
if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process


import json
import csv
import time
import re
import bs4
from collections import OrderedDict
from datetime import datetime, timedelta as td
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.template import loader
from django.utils.encoding import smart_str

from lexicon_miner.models import Lexicon,Word
from conceptualiser.models import Term, TermConcept
from searcher.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from .agg_manager import AggManager
from .cluster_manager import ClusterManager
from .fact_manager import FactManager
from utils.highlighter import Highlighter, ColorPicker
from utils.autocomplete import Autocomplete
from dataset_importer.document_preprocessor.preprocessor import DocumentPreprocessor, preprocessor_map
from task_manager.views import task_params
from task_manager.models import Task

from texta.settings import STATIC_URL, URL_PREFIX, date_format, es_links, INFO_LOGGER, ERROR_LOGGER

from searcher.view_functions.export_pages import export_pages
from searcher.view_functions.tranlist_highlighting import transliterate_highlight_spans, highlight_transliterately


try:
    from io import BytesIO # NEW PY REQUIREMENT
except:
    from io import StringIO # NEW PY REQUIREMENT


def ngrams(input_list, n):
  return zip(*[input_list[i:] for i in range(n)])


def convert_date(date_string,frmt):
    return datetime.strptime(date_string,frmt).date()


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        value['key'] = key
        entries.append(value)

    return entries


def get_fields(es_m):
    """ Create field list from fields in the Elasticsearch mapping
    """
    reserved_fields = ['texta_facts']
    fields = []
    mapped_fields = es_m.get_mapped_fields()
    
    print(es_m)

    for data in [x for x in mapped_fields if x['path'] not in reserved_fields]:
        path = data['path']

        if data['type'] == 'date':
            data['range'] = get_daterange(es_m,path)

        path_list = path.split('.')
        label = '{0} --> {1}'.format(path_list[0], ' --> '.join(path_list[1:])) if len(path_list) > 1 else path_list[0]
        label = label.replace('-->', u'→')

        field = {'data': json.dumps(data), 'label': label, 'type': data['type']}
        fields.append(field)

        # Add additional field if it has fact
        has_facts, has_fact_str_val, has_fact_num_val =  es_m.check_if_field_has_facts(path_list)

        if has_facts:
            data['type'] = 'facts'
            field = {'data': json.dumps(data), 'label': label + ' [fact_names]', 'type':'facts'}
            fields.append(field)

        if has_fact_str_val:
            data['type'] = 'fact_str_val'
            field = {'data': json.dumps(data), 'label': label + ' [fact_text_values]', 'type':'fact_str_val'}
            fields.append(field)

        if has_fact_num_val:
            data['type'] = 'fact_num_val'
            field = {'data': json.dumps(data), 'label': label + ' [fact_num_values]', 'type':'fact_num_val'}
            fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])
    return fields


def get_daterange(es_m,field):
    min_val,max_val = es_m.get_extreme_dates(field)
    return {'min':min_val[:10],'max':max_val[:10]}


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
                       'dataset': ds.get_index(),
                       'language_models': language_models, 
                       'allowed_datasets': datasets,                       
                       'enabled_preprocessors': enabled_preprocessors,
                       'task_params': task_params}

    template = loader.get_template('searcher.html')

    return HttpResponse(template.render(template_params, request))


@login_required
def get_query(request):
    es_params = request.POST
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    # GET ONLY MAIN QUERY
    query = es_m.combined_query['main']
    return HttpResponse(json.dumps(query))


def zero_list(n):
    listofzeros = [0] * n
    return listofzeros

# Unused?
def display_encode(s):
    try:
        return s.encode('latin1')
    except Exception as e:
        print(e)
        #TODO: What is the intention here?  Why is latin1 first? What are the appropriate exceptions instead of catchall)
        return s.encode('utf8')


@login_required
def save(request):
    logger = LogManager(__name__, 'SAVE SEARCH')

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    es_params = request.POST
    es_m.build(es_params)
    combined_query = es_m.get_combined_query()

    try:
        q = combined_query
        desc = request.POST['search_description']
        s_content = json.dumps([request.POST[x] for x in request.POST.keys() if 'match_txt' in x])
        search = Search(author=request.user,search_content=s_content,description=desc,dataset=Dataset.objects.get(pk=int(request.session['dataset'])),query=json.dumps(q))
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
    ### TODO REDO THIS
    return HttpResponse()
    #active_dataset_ids = [int(ds) for ds in request.session['dataset']]
    #datasets = Dataset.objects.filter(pk__in=[request.session['dataset']])
    
    #print(list(datasets))

    #searches = Search.objects.filter(author=request.user).filter(dataset__in=[])
    
    #return HttpResponse(json.dumps([{'id':search.pk,'desc':search.description} for search in searches],ensure_ascii=False))


@login_required
def get_table_header(request):
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    # get columns names from ES mapping
    fields = es_m.get_column_names()
    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'searches': Search.objects.filter(author=request.user),
                       'columns': [{'index':index, 'name':field_name} for index, field_name in enumerate(fields)],
                       'dataset': ds.get_index(),
                       'mapping': ds.get_mapping()}
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


def merge_spans(spans):
    """ Merge spans range
    """
    merged_spans = []
    sort_spans = sorted(spans, key=lambda l:l[0])
    total_spans = len(sort_spans)
    if total_spans:
        merged_spans.append(sort_spans[0])
        i = 1
        while i < total_spans:
            m_last = list(merged_spans[-1])
            s_next = list(sort_spans[i])
            if s_next[0] > m_last[1]:
                merged_spans.append(s_next)
            if (s_next[0] <= m_last[1]) and (s_next[1] > m_last[1]):
                merged_spans[-1] = [m_last[0], s_next[1]]
            i += 1
    return merged_spans

@login_required
def mlt_query(request):
    logger = LogManager(__name__, 'SEARCH MLT')
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

    ds = Datasets().activate_dataset(request.session)
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

def get_fields_content(hit,fields):
    row = {}
    for field in fields:
        if 'highlight' in hit:
            field_content = hit['highlight']
        else:
            field_content = hit['_source']

        try:
            for field_element in field.split('.'):
                field_content = field_content[field_element]
        except KeyError:
            field_content = ''

        if type(field_content) == list:
            field_content = '<br><br>'.join(field_content)

        row[field] = field_content

    return row

@login_required
def cluster_query(request):
    params = request.POST
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(params)

    cluster_m = ClusterManager(es_m,params)
    clustering_data = convert_clustering_data(cluster_m, params)

    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'clusters': clustering_data}

    template = loader.get_template('cluster_results.html')
    return HttpResponse(template.render(template_params, request))


def convert_clustering_data(cluster_m, params):
    out = []
    clusters = cluster_m.clusters

    for cluster_id,cluster_content in clusters.items():
        documents = [cluster_m.documents[doc_id] for doc_id in cluster_content]
        cluster_label = 'Cluster {0} ({1})'.format(cluster_id+1,len(cluster_content))
        keywords = cluster_m.cluster_keywords[cluster_id]
        cluster_data = {'documents':highlight_cluster_keywords(documents,keywords, params),
                        'label':cluster_label,
                        'id':cluster_id,
                        'keywords':' '.join(keywords)}
        out.append(cluster_data)
    return out


def highlight_cluster_keywords(documents, keywords, params):
    out = []
    for document in documents:
        to_highlighter = []
        for keyword in keywords:
            pattern = re.compile(u'{0}{1}{2}'.format(u'(?<![A-z0-9])',re.escape(keyword.lower()),u'(?![A-z0-9])'))
            for match in pattern.finditer(document.lower()):
                span = [(match.start(),match.end())]
                new_match = {u'spans':span,u'color':u'#FFD119'}
                to_highlighter.append(new_match)

        if to_highlighter:
            hl = Highlighter(default_category='[HL]')
            document = hl.highlight(document,to_highlighter)
            if 'show_short_version_cluster' in params.keys():
                document = additional_option_cut_text(document, params['short_version_n_char_cluster'])
            out.append(document)
        elif not 'show_unhighlighted' in params.keys():
            out.append(document)

    return out


def search(es_params, request):
    logger = LogManager(__name__, 'SEARCH CORPUS')

    try:

        start_time = time.time()
        out = {'column_names': [],
               'aaData': [],
               'iTotalRecords': 0,
               'iTotalDisplayRecords': 0,
               'lag': 0}

        ds = Datasets().activate_dataset(request.session)
        es_m = ds.build_manager(ES_Manager)
        es_m.build(es_params)

        # DEFINING THE EXAMPLE SIZE
        es_m.set_query_parameter('from', es_params['examples_start'])
        es_m.set_query_parameter('size', es_params['num_examples'])

        # HIGHLIGHTING THE MATCHING FIELDS
        pre_tag = '<span class="[HL]" style="background-color:#FFD119">'
        post_tag = "</span>"
        highlight_config = {"fields": {}, "pre_tags": [pre_tag], "post_tags": [post_tag]}
        for field in es_params:
            if 'match_field' in field and es_params['match_operator_'+field.split('_')[-1]] != 'must_not':
                f = es_params[field]
                highlight_config['fields'][f] = {"number_of_fragments": 0}
        es_m.set_query_parameter('highlight', highlight_config)
        response = es_m.search()

        out['iTotalRecords'] = response['hits']['total']
        out['iTotalDisplayRecords'] = response['hits']['total'] # number of docs

        if int(out['iTotalDisplayRecords']) > 10000: # Allow less pages if over page limit
            out['iTotalDisplayRecords'] = '10000'

        # get columns names from ES mapping
        out['column_names'] = es_m.get_column_names()

        for hit in response['hits']['hits']:
            hit_id = str(hit['_id'])
            row = OrderedDict([(x, '') for x in out['column_names']]) # OrderedDict to remember column names with their content

            inner_hits = hit['inner_hits'] if 'inner_hits' in hit else {}
            name_to_inner_hits = defaultdict(list)
            for inner_hit_name, inner_hit in inner_hits.items():
                hit_type, _, _ = inner_hit_name.rsplit('_', 2)
                for inner_hit_hit in inner_hit['hits']['hits']:
                    source = inner_hit_hit['_source']
                    source['hit_type'] = hit_type
                    name_to_inner_hits[source['doc_path']].append(source)


            # Fill the row content respecting the order of the columns
            cols_data = {}
            for col in out['column_names']:

                # If the content is nested, need to break the flat name in a path list
                filed_path = col.split('.')

                # Get content for this field path:
                #   - Starts with the hit structure
                #   - For every field in field_path, retrieve the specific content
                #   - Repeat this until arrives at the last field
                #   - If the field in the field_path is not in this hit structure,
                #     make content empty (to allow dynamic mapping without breaking alignment)
                content = hit['_source']
                for p in filed_path:
                    if col == u'texta_facts' and p in content:
                        new_content = []
                        facts = ['{ "'+x["fact"]+'": "'+x["str_val"]+'"}' for x in sorted(content[p], key=lambda k: k['fact'])]
                        fact_counts = Counter(facts)

                        facts = sorted(list(set(facts)))
                        facts_dict = [json.loads(x) for x in facts]
                        for i, d in enumerate(facts_dict):
                            for k in d:
                                # Make factnames bold for searcher
                                if '<b>'+k+'</b>' not in new_content:
                                    new_content.append('<b>'+k+'</b>')
                                new_content.append('    {}: {}'.format(d[k], fact_counts[facts[i]]))
                        content = '\n'.join(new_content)
                    else:
                        content = content[p] if p in content else ''


                # To strip fields with whitespace in front
                try:
                    old_content = content.strip()
                except:
                    old_content = content

                # Substitute feature value with value highlighted by Elasticsearch
                if col in highlight_config['fields'] and 'highlight' in hit:
                    content = hit['highlight'][col][0]
                # Prettify and standardize highlights
                if name_to_inner_hits[col]:
                    highlight_data = []
                    color_map = ColorPicker.get_color_map(keys={hit['fact'] for hit in name_to_inner_hits[col]})
                    for inner_hit in name_to_inner_hits[col]:
                        datum = {
                            'spans': json.loads(inner_hit['spans']),
                            'name': inner_hit['fact'],
                            'category': '[{0}]'.format(inner_hit['hit_type']),
                            'color': color_map[inner_hit['fact']]
                        }

                        if inner_hit['hit_type'] == 'fact_val':
                            datum['value'] = inner_hit['str_val']
                        highlight_data.append(datum)

                    content = Highlighter(average_colors=True, derive_spans=True,
                                              additional_style_string='font-weight: bold;').highlight(
                                                  old_content,
                                                  highlight_data,
                                                  tagged_text=content)
                else:
                    # WHEN USING OLD FORMAT DOCUMENTS, SOMETIMES BREAKS AT HIGHLIGHTER, CHECK IF ITS STRING INSTEAD OF FOR EXAMPLE LIST
                    highlight_data = []
                    if (isinstance(content, str)) or (isinstance(content, bytes)):
                        content = Highlighter(average_colors=True, derive_spans=True,
                                                additional_style_string='font-weight: bold;').highlight(
                                                    old_content,
                                                    highlight_data,
                                                    tagged_text=content)
                # Append the final content of this col to the row
                if(row[col] == ''):
                    row[col] = content

                cols_data[col] = {'highlight_data': highlight_data, 'content': content, 'old_content': old_content}


            # Transliterate the highlighting between different cols
            translit_search_cols = ['text', 'translit', 'lemmas']
            hl_cols = [x for x in cols_data if len(x.split('.')) > 1 and x.split('.')[-1] in translit_search_cols] # To get value before '.' as well
            row = highlight_transliterately(cols_data, row, hl_cols=hl_cols)

            # Checks if user wants to see full text or short version
            for col in row:
                if 'show_short_version' in es_params.keys():
                    row[col] = additional_option_cut_text(row[col], es_params['short_version_n_char'])

            out['aaData'].append(row.values())

            out['lag'] = time.time()-start_time
            logger.set_context('query', es_m.get_combined_query())
            logger.set_context('user_name', request.user.username)
            logger.info('documents_queried')

        return out

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process': 'SEARCH DOCUMENTS', 'event': 'documents_queried_failed'}), exc_info=True)

        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.set_context('user_name', request.user.username)
        logger.error('documents_queried_failed')

        out = {'column_names': [], 'aaData': [], 'iTotalRecords': 0, 'iTotalDisplayRecords': 0, 'lag': 0}
        return out


def additional_option_cut_text(content, window_size):
    window_size = int(window_size)
    
    if not content:
        return ''
    
    if not isinstance(content, str):
        return content

    if '[HL]' in content:
        soup = bs4.BeautifulSoup(content,'lxml')
        html_spans = soup.find_all('span')

        html_spans_merged = []
        num_spans = len(html_spans)
        # merge together ovelapping spans
        for i,html_span in enumerate(html_spans):
            if not html_span.get('class'):
                span_text = html_span.text
                span_tokens = span_text.split(' ')
                span_tokens_len = len(span_tokens)
                if i == 0:
                    if span_tokens_len > window_size:
                        new_text = u' '.join(span_tokens[-window_size:])
                        new_text = u'... {0}'.format(new_text)
                        html_span.string = new_text
                    html_spans_merged.append(str(html_span))
                elif i == num_spans-1:
                    if span_tokens_len > window_size:
                        new_text = u' '.join(span_tokens[:window_size])
                        new_text = u'{0} ...'.format(new_text)
                        html_span.string = new_text
                    html_spans_merged.append(str(html_span))
                else:
                    if span_tokens_len > window_size:
                        new_text_left = u' '.join(span_tokens[:window_size])
                        new_text_right = u' '.join(span_tokens[-window_size:])
                        new_text = u'{0} ...\n... {1}'.format(new_text_left,new_text_right)
                        html_span.string = new_text
                    html_spans_merged.append(str(html_span))
            else:
                html_spans_merged.append(str(html_span))

        return ''.join(html_spans_merged)
    else:
        return content


@login_required
def remove_by_query(request):
    es_params = request.POST

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    Process(target=remove_worker,args=(es_m,'notimetothink')).start()

    return HttpResponse(True)


def remove_worker(es_m, dummy):
    response = es_m.delete()
    # TODO: add logging


@login_required
def aggregate(request):
    agg_m = AggManager(request)
    data = agg_m.output_to_searcher()
    return HttpResponse(json.dumps(data))


@login_required
def delete_facts(request):
    fact_m = FactManager(request)
    Process(target=fact_m.remove_facts_from_document, args=(dict(request.POST),)).start()

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

def _get_facts_agg_count(es_m, facts):
    counts = {}
    doc_ids = set()
    response = es_m.scroll()
    total_docs = response['hits']['total']
    scroll_id = response['_scroll_id']
    while total_docs > 0:
        response = es_m.scroll(scroll_id=scroll_id)
        total_docs = len(response['hits']['hits'])
        scroll_id = response['_scroll_id']
        for hit in response['hits']['hits']:
            doc_ids.add(hit['_id'])
    # Count the intersection ids
    for k in facts.keys():
        counts[k] = len(facts[k] & doc_ids)
    return counts


def facts_agg(es_params, request):
    logger = LogManager(__name__, 'FACTS AGGREGATION')

    distinct_values = []
    query_results = []
    lexicon = []
    aggregation_data = es_params['aggregate_over']
    aggregation_data = json.loads(aggregation_data)
    original_aggregation_field = aggregation_data['path']
    aggregation_field = 'texta_link.facts'

    try:
        aggregation_size = 50
        aggregations = {"strings": {es_params['sort_by']: {"field": aggregation_field, 'size': 0}},
                        "distinct_values": {"cardinality": {"field": aggregation_field}}}

        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        dataset = ds.get_index()
        mapping = ds.get_mapping()
        date_range = ds.get_date_range()
        es_m = ES_Manager(dataset, mapping, date_range)

        for item in es_params:
            if 'saved_search' in item:
                s = Search.objects.get(pk=es_params[item])
                name = s.description
                saved_query = json.loads(s.query)
                es_m.load_combined_query(saved_query)
                es_m.set_query_parameter('aggs', aggregations)
                response = es_m.search()

                # Filter response
                bucket_filter = '{0}.'.format(original_aggregation_field.lower())
                final_bucket = []
                for b in response['aggregations']['strings']['buckets']:
                    if bucket_filter in b['key']:
                        fact_name = b['key'].split('.')[-1]
                        b['key'] = fact_name
                        final_bucket.append(b)
                final_bucket = final_bucket[:aggregation_size]
                response['aggregations']['distinct_values']['value'] = len(final_bucket)
                response['aggregations']['strings']['buckets'] = final_bucket

                normalised_counts,labels = normalise_agg(response, es_m, es_params, 'strings')
                lexicon = list(set(lexicon+labels))
                query_results.append({'name':name,'data':normalised_counts,'labels':labels})
                distinct_values.append({'name':name,'data':response['aggregations']['distinct_values']['value']})


        es_m.build(es_params)
        # FIXME
        # this is confusing for the user
        if not es_m.is_combined_query_empty():
            es_m.set_query_parameter('aggs', aggregations)
            response = es_m.search()

            # Filter response
            bucket_filter = '{0}.'.format(original_aggregation_field.lower())
            final_bucket = []
            for b in response['aggregations']['strings']['buckets']:
                if bucket_filter in b['key']:
                    fact_name = b['key'].split('.')[-1]
                    b['key'] = fact_name
                    final_bucket.append(b)
            final_bucket = final_bucket[:aggregation_size]
            response['aggregations']['distinct_values']['value'] = len(final_bucket)
            response['aggregations']['strings']['buckets'] = final_bucket

            normalised_counts,labels = normalise_agg(response, es_m, es_params, 'strings')
            lexicon = list(set(lexicon+labels))
            query_results.append({'name':'Query','data':normalised_counts,'labels':labels})
            distinct_values.append({'name':'Query','data':response['aggregations']['distinct_values']['value']})

        data = [a+zero_list(len(query_results)) for a in map(list, zip(*[lexicon]))]
        data = [['Word']+[query_result['name'] for query_result in query_results]]+data

        for i,word in enumerate(lexicon):
            for j,query_result in enumerate(query_results):
                for k,label in enumerate(query_result['labels']):
                    if word == label:
                        data[i+1][j+1] = query_result['data'][k]

        logger.set_context('user_name', request.user.username)
        logger.info('facts_aggregation_queried')

    except Exception as e:
        print('-- Exception[{0}] {1}'.format(__name__, e))
        logger.set_context('user_name', request.user.username)
        logger.exception('facts_aggregation_query_failed')

    table_height = len(data)*15
    table_height = table_height if table_height > 500 else 500
    return {'data':[data[0]]+sorted(data[1:], key=lambda x: sum(x[1:]), reverse=True),'height':table_height,'type':'bar','distinct_values':json.dumps(distinct_values)}


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


def extract_constraints(query):
    """Extracts GUI search field values from Elasticsearch query.
    """
    constraints = []

    if 'should' in query['main']['query']['bool'] and query['main']['query']['bool']['should']:
        for raw_constraint in query['main']['query']['bool']['should']:
            constraints.append(_extract_string_constraint(raw_constraint))


    if 'must' in query['main']['query']['bool'] and query['main']['query']['bool']['must']:
        range_constraints = []

        for raw_constraint_idx, raw_constraint in enumerate(query['main']['query']['bool']['must']):
            if 'range' in raw_constraint:
                range_constraints.append((raw_constraint_idx, raw_constraint))
            elif 'bool' in raw_constraint:
                if list(raw_constraint['bool'].values())[0][0]['nested']['inner_hits']['name'].startswith('fact_val'):   # fact val query
                    constraints.append(_extract_fact_val_constraint(raw_constraint))
                else:   # fact query
                    constraints.append(_extract_fact_constraint(raw_constraint))

        constraints.extend(_extract_date_constraints(range_constraints))

    return constraints

def _extract_string_constraint(raw_constraint):
    operator = list(raw_constraint['bool'].keys())[0]
    field = None
    match_type = None
    constraint_content = []
    slop = None

    for entry in raw_constraint['bool'][operator]:
        constraint_details = list(entry['bool']['should'])[0]
        match_type = list(constraint_details.keys())[0]
        field = list(constraint_details[match_type].keys())[0]
        content = constraint_details[match_type][field]['query']
        slop = constraint_details[match_type][field]['slop']
        constraint_content.append(content)

    return {
        'constraint_type': 'string',
        'operator': operator,
        'field': field,
        'match_type': match_type,
        'content': constraint_content,
        'slop': slop
    }


def _extract_date_constraints(range_constraint_idx_range_constraint_pairs):
    date_ranges = []

    new_range = None
    last_idx = -1
    last_comparative_operator = 'lte'
    last_field = None

    for range_constraint_idx, range_constraint in range_constraint_idx_range_constraint_pairs:
        current_field = list(range_constraint['range'].keys())[0]
        if 'gte' in range_constraint['range'][current_field]:
            if last_field is not None:
                date_ranges.append(new_range)
            new_range = {
                'start_date': range_constraint['range'][current_field]['gte'],
                'field': current_field,
                'constraint_type': 'date'
            }

            last_comparative_operator = 'gte'
        elif 'lte' in range_constraint['range'][current_field]:
            if not (range_constraint_idx - 1 == last_idx and last_comparative_operator == 'gte' and
                            current_field == last_field) and last_field is not None:
                date_ranges.append(new_range)
            elif last_field is None:
                new_range = {
                    'field': current_field,
                    'constraint_type': 'date'
                }

            new_range['end_date'] = range_constraint['range'][current_field]['lte']

            last_comparative_operator = 'lte'

        last_field = current_field
        last_idx = range_constraint_idx

    if new_range:
        date_ranges.append(new_range)

    return date_ranges


def _extract_fact_constraint(raw_constraint):
    operator = list(raw_constraint['bool'].keys())[0]
    content = []
    field = None

    for entry in raw_constraint['bool'][operator]:
        field = list(entry['nested']['query']['bool']['must'][0]['term'].values())[0]
        content.append(list(entry['nested']['query']['bool']['must'][1]['term'].values())[0])

    return {
        'constraint_type': 'facts',
        'operator': operator,
        'field': field,
        'content': content
    }

def _extract_fact_val_constraint(raw_constraint):
    operator = list(raw_constraint['bool'].keys())[0]
    field = None
    sub_constraints = []

    for entry in raw_constraint['bool'][operator]:
        fact_name = None
        fact_val_operator = None
        fact_val = None
        constraint_type = None

        for sub_entry in entry['nested']['query']['bool']['must']:
            if 'texta_facts.doc_path' in sub_entry['match']:
                field = sub_entry['match']['texta_facts.doc_path']
            elif 'texta_facts.fact' in sub_entry['match']:
                fact_name = sub_entry['match']['texta_facts.fact']
            elif 'texta_facts.str_val' in sub_entry['match']:
                fact_val = sub_entry['match']['texta_facts.str_val']
                fact_val_operator = '='
                constraint_type = 'str_fact_val'
            elif 'texta_facts.num_val' in sub_entry['match']:
                fact_val = sub_entry['match']['texta_facts.num_val']
                fact_val_operator = '='
                constraint_type = 'num_fact_val'

        if fact_val == None:
            if 'must_not' in entry['nested']['query']['bool']:
                if 'texta_facts.str_val' in entry['nested']['query']['bool']['must_not'][0]['match']:
                    fact_val = entry['nested']['query']['bool']['must_not'][0]['match']['texta_facts.str_val']
                    fact_val_operator = '!='
                    constraint_type = 'str_fact_val'
                else:
                    fact_val = entry['nested']['query']['bool']['must_not'][0]['match']['texta_facts.num_val']
                    fact_val_operator = '!='
                    constraint_type = 'num_fact_val'

        sub_constraints.append({
            'fact_name': fact_name,
            'fact_val': fact_val,
            'fact_val_operator': fact_val_operator
        })

    return {
        'constraint_type': constraint_type,
        'operator': operator,
        'field': field,
        'sub_constraints': sub_constraints
    }

@login_required
def fact_graph(request):

    search_size = int(request.POST['fact_graph_size'])

    fact_m = FactManager(request)
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
    return HttpResponse(template.render(template_params, request))

