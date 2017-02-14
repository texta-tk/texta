# -*- coding: utf8 -*-
import calendar
import threading
import json
import csv
import time
from datetime import datetime, timedelta as td

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, StreamingHttpResponse
from django.template import loader
from django.utils.encoding import smart_str

from conceptualiser.models import Term, TermConcept
from corpus_tool.models import Search
from permission_admin.models import Dataset
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from utils.agg_manager import AggManager

from texta.settings import STATIC_URL, URL_PREFIX, date_format, es_links

ES_SCROLL_BATCH = 100

try:
    from cStringIO import StringIO
except:
    from StringIO import StringIO


def ngrams(input_list, n):
  return zip(*[input_list[i:] for i in range(n)])


def convert_date(date_string,frmt):
    return datetime.strptime(date_string,frmt).date()


def get_fields(es_m):
    """ Crete field list from fields in the Elasticsearch mapping
    """
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for data in mapped_fields:
        path = data['path']
        path_list = path.split('.')
        label = '{0} --> {1}'.format(path_list[0], ' --> '.join(path_list[1:])) if len(path_list) > 1 else path_list[0]
        label = label.replace('-->', u'→')
        field = {'data': json.dumps(data), 'label': label, 'type': data['type']}
        fields.append(field)

        # Add additional field if it has fact
        if es_m.check_if_field_has_facts(path_list):
            data['type'] = 'facts'
            label += ' [facts]'
            field = {'data': json.dumps(data), 'label': label, 'type':'facts'}
            fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])

    return fields


@login_required
def index(request):

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    fields = get_fields(es_m)

    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'date_range': ds.get_date_range(),
                       'searches': Search.objects.filter(author=request.user),
                       'dataset': ds.get_index()}

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


def date_ranges(date_range,interval):
    frmt = "%Y-%m-%d"
    
    ranges = []
    labels = []

    date_min = convert_date(date_range['min'],frmt)
    date_max = convert_date(date_range['max'],frmt)
    
    if interval == 'year':
        for yr in range(date_min.year,date_max.year+1):
            ranges.append({'from':str(yr)+'-01-01','to':str(yr+1)+'-01-01'})
            labels.append(yr)
    if interval == 'quarter':
        for yr in range(date_min.year,date_max.year+1):
            for i,quarter in enumerate([(1,3),(4,6),(7,9),(10,12)]):
                end = calendar.monthrange(yr,quarter[1])[1]
                ranges.append({'from':'-'.join([str(yr),str(quarter[0]),'01']),'to':'-'.join([str(yr),str(quarter[1]),str(end)])})
                labels.append('-'.join([str(yr),str(i+1)+'Q']))
    if interval == 'month':
        for yr in range(date_min.year,date_max.year+1):
            for month in range(1,13):
                month_max = str(calendar.monthrange(yr,month)[1])
                if month < 10:
                    month = '0'+str(month)
                else:
                    month = str(month)
                ranges.append({'from':'-'.join([str(yr),month,'01']),'to':'-'.join([str(yr),month,month_max])})
                labels.append('-'.join([str(yr),month]))
    if interval == 'day':
        d1 = date_min
        d2 = date_max+td(days=1)
        delta = d2-d1
        dates = [d1+td(days=i) for i in range(delta.days+1)]
        for date_pair in ngrams(dates,2):
            ranges.append({'from':date_pair[0].strftime(frmt),'to':date_pair[1].strftime(frmt)})
            labels.append(date_pair[0].strftime(frmt))

    return ranges,labels


def zero_list(n):
    listofzeros = [0] * n
    return listofzeros


def display_encode(s):
    try:
        return s.encode('latin1')
    except Exception as e:
        print e
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
        search = Search(author=request.user,description=desc,dataset=Dataset.objects.get(pk=int(request.session['dataset'])),query=json.dumps(q))
        search.save()
        logger.set_context('user_name', request.user.username)
        logger.set_context('search_id', search.id)
        logger.info('search_saved')

    except Exception as e:
        print '-- Exception[{0}] {1}'.format(__name__, e)
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
        print '-- Exception[{0}] {1}'.format(__name__, e)
        logger.exception('search_deletion_failed')

    return HttpResponse(search_id)


def autocomplete(request):

    lookup_type = request.POST['lookup_type']
    field_name = request.POST['field_name']
    field_id = request.POST['id']
    content = request.POST['content']

    autocomplete_data = {}
    if 'autocomplete_data' in request.session:
        autocomplete_data = request.session['autocomplete_data']

    suggestions = []

    if (lookup_type in autocomplete_data) and (field_name in autocomplete_data[lookup_type].keys()):
        for term in autocomplete_data[lookup_type][field_name]:
            term = smart_str(term)
            insert_function = "insert('','{0}','{1}','{2}');".format(field_id, term, lookup_type)
            html_suggestion = '<li class="list-group-item" onclick="{0}">{1}</li>'.format(insert_function, term)
            suggestions.append(html_suggestion)
    else:

        last_line = content.split('\n')[-1] if content else ''

        if len(last_line) > 0:
            terms = Term.objects.filter(term__startswith=last_line).filter(author=request.user)
            seen = {}
            suggestions = []
            for term in terms[:10]:
                for term_concept in TermConcept.objects.filter(term=term.pk):
                    concept = term_concept.concept
                    concept_term = (concept.pk,term.term)
                    if concept_term not in seen:
                        seen[concept_term] = True
                        display_term = term.term.replace(last_line,'<font color="red">'+last_line+'</font>')
                        display_text = "<b>"+smart_str(display_term)+"</b> @"+smart_str(concept.pk)+"-"+smart_str(concept.descriptive_term.term)
                        suggestions.append("<li class=\"list-group-item\" onclick=\"insert('"+str(concept.pk)+"','"+str(field_id)+"','"+smart_str(concept.descriptive_term.term)+"');\">"+display_text+"</li>")

    return HttpResponse(suggestions)


@login_required
def get_saved_searches(request):  
    searches = Search.objects.filter(author=request.user).filter(dataset=Dataset(pk=int(request.session['dataset'])))
    return HttpResponse(json.dumps([{'id':search.pk,'desc':search.description} for search in searches],ensure_ascii=False))


@login_required
def get_table_header(request):
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    # get columns names from ES mapping
    fields = es_m.get_column_names()
    template_params = {'STATIC_URL': STATIC_URL,
                       'URL_PREFIX': URL_PREFIX,
                       'fields': fields,
                       'date_range': ds.get_date_range(),
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
        pre_tag = "<span style='background-color:#FFD119'>"
        post_tag = "</span>"
        highlight_config = {"fields": {}, "pre_tags": [pre_tag], "post_tags": [post_tag]}
        for field in es_params:
            if 'match_field' in field and es_params['match_operator_'+field.split('_')[-1]] != 'must_not':
                f = es_params[field]
                highlight_config['fields'][f] = {"number_of_fragments": 0}
        es_m.set_query_parameter('highlight', highlight_config)

        response = es_m.search()

        # Get the ids of all documents to be presented in the results page
        doc_hit_ids = []
        for hit in response['hits']['hits']:
            hit_id = str(hit['_id'])
            doc_hit_ids.append(hit_id)
        # Use the doc_ids to restrict the facts search (fast!)
        facts_map = es_m.get_facts_map(doc_ids=doc_hit_ids)
        facts_highlight = facts_map['include']

        out['iTotalRecords'] = response['hits']['total']
        out['iTotalDisplayRecords'] = response['hits']['total']

        # get columns names from ES mapping
        out['column_names'] = es_m.get_column_names()

        for hit in response['hits']['hits']:

            hit_id = str(hit['_id'])
            row = []
            
            # Fill the row content respecting the order of the columns
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
                    content = content[p] if p in content else ''

                # If has facts, highlight
                if hit_id in facts_highlight and col in facts_highlight[hit_id]:
                    fact_spans = facts_highlight[hit_id][col]
                    # Merge overlapping spans
                    fact_spans = merge_spans(fact_spans)
                    rest_sentence = content
                    corpus_facts = ''
                    last_cut = 0
                    # Apply span tagging
                    for span in fact_spans:
                        start = span[0] - last_cut
                        end = span[1] - last_cut
                        b_sentence = rest_sentence[0:start]
                        f_sencente = rest_sentence[start:end]
                        rest_sentence = rest_sentence[end:]
                        last_cut = span[1]
                        corpus_facts += b_sentence
                        corpus_facts += "<span style='background-color:#A3E4D7'>"
                        corpus_facts += f_sencente
                        corpus_facts += "</span>"
                    corpus_facts += rest_sentence
                    content = corpus_facts

                # If content in the highlight structure, replace it with the tagged hit['highlight']
                if col in highlight_config['fields'] and 'highlight' in hit:
                    content = hit['highlight'][col][0]

                # CHECK FOR EXTERNAL RESOURCES
                link_key = (ds.get_index(), ds.get_mapping(), col)
                if link_key in es_links:
                    link_prefix, link_suffix = es_links[link_key]
                    content = '<a href="'+str(link_prefix)+str(content)+str(link_suffix)+'" target="_blank">'+str(content)+'</a>'

                # Append the final content of this col to the row
                row.append(content)

            out['aaData'].append(row)

        out['lag'] = time.time()-start_time
        logger.set_context('query', es_m.get_combined_query())
        logger.set_context('user_name', request.user.username)
        logger.info('documents_queried')

        return out

    except Exception, e:
        print '-- Exception[{0}] {1}'.format(__name__, e)
        logger.set_context('user_name', request.user.username)
        logger.exception('documents_queried_failed')

        out = {'column_names': [], 'aaData': [], 'iTotalRecords': 0, 'iTotalDisplayRecords': 0, 'lag': 0}
        return out


@login_required
def export_pages(request):

    es_params = {entry['name']: entry['value'] for entry in json.loads(request.GET['args'])}

    if es_params['num_examples'] == '*':
        response = StreamingHttpResponse(get_all_rows(es_params, request), content_type='text/csv')
    else:
        response = StreamingHttpResponse(get_rows(es_params, request), content_type='text/csv')
    
    response['Content-Disposition'] = 'attachment; filename="%s"' % (es_params['filename'])

    return response


def get_rows(es_params, request):

    buffer_ = StringIO()
    writer = csv.writer(buffer_)
    
    writer.writerow(es_params['features'])

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    es_m.set_query_parameter('from', es_params['examples_start'])
    q_size = es_params['num_examples'] if es_params['num_examples'] <= ES_SCROLL_BATCH else ES_SCROLL_BATCH
    es_m.set_query_parameter('size', q_size)

    features = {feature: None for feature in es_params['features'] }

    response = es_m.scroll()

    scroll_id = response['_scroll_id']
    left = es_params['num_examples']
    hits = response['hits']['hits']
    
    while hits and left:
        rows = []
        for hit in hits:
            row = []
            for field,content in sorted(hit['_source'].items(),key = lambda x: x[0]):
                if field in features:
                    row.append(content)
            rows.append(row)

        if left > len(rows):
            for row in rows:
                writer.writerow([element.encode('utf-8') if isinstance(element,unicode) else element for element in row])
            buffer_.seek(0)
            data = buffer_.read()
            buffer_.seek(0)
            buffer_.truncate()
            yield data
            
            left -= len(rows)
            response = es_m.scroll(scroll_id=scroll_id)
            hits = response['hits']['hits']
            scroll_id = response['_scroll_id']

        elif left == len(rows):
            for row in rows:
                writer.writerow([element.encode('utf-8') if isinstance(element,unicode) else element for element in row])
            buffer_.seek(0)
            data = buffer_.read()
            buffer_.seek(0)
            buffer_.truncate()
            yield data
            
            break
        else:
            for row in rows[:left]:
                writer.writerow([element.encode('utf-8') if isinstance(element,unicode) else element for element in row])
            buffer_.seek(0)
            data = buffer_.read()
            buffer_.seek(0)
            buffer_.truncate()
            yield data
            
            break


def get_all_rows(es_params, request):
    buffer_ = StringIO()
    writer = csv.writer(buffer_)
    
    writer.writerow(es_params['features'])

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    es_m.set_query_parameter('size', ES_SCROLL_BATCH)

    features = {feature: None for feature in es_params['features']}

    response = es_m.scroll()

    scroll_id = response['_scroll_id']
    hits = response['hits']['hits']
    
    while hits:
        for hit in hits:
            row = []
            for field,content in sorted(hit['_source'].items(),key = lambda x: x[0]):
                if field in features:
                    row.append(content)
            writer.writerow([element.encode('utf-8') if isinstance(element,unicode) else element for element in row])
        
        buffer_.seek(0)
        data = buffer_.read()
        buffer_.seek(0)
        buffer_.truncate()
        yield data

        response = es_m.scroll(scroll_id=scroll_id)
        hits = response['hits']['hits']
        scroll_id = response['_scroll_id']


def remove_by_query(request):
    es_params = request.POST

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    
    threading.Thread(target=remove_worker,args=(es_m,'notimetothink')).start()
    return HttpResponse(True)


def remove_worker(es_m,dummy):
    response = es_m.delete()
    # TODO: add logging


def aggregate(request):

    agg_m = AggManager(request)
    data = agg_m.output_to_searcher()

    return HttpResponse(json.dumps(data))


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

    except Exception, e:
        print '-- Exception[{0}] {1}'.format(__name__, e)
        logger.set_context('user_name', request.user.username)
        logger.exception('facts_aggregation_query_failed')

    table_height = len(data)*15
    table_height = table_height if table_height > 500 else 500
    return {'data':[data[0]]+sorted(data[1:], key=lambda x: sum(x[1:]), reverse=True),'height':table_height,'type':'bar','distinct_values':json.dumps(distinct_values)}


def normalise_agg(response, es_m, es_params, agg_type):

    raw_counts = [bucket['doc_count'] for bucket in response['aggregations'][agg_type]['buckets']]
    bucket_labels = []
    if agg_type == 'strings':
        for a in response['aggregations']['strings']['buckets']:
            try:
                bucket_labels.append(a['key'])
            except KeyError:
                bucket_labels.append(smart_str(a['key']))

    if es_params['frequency_normalisation'] == 'relative_frequency':

        es_m.set_query_parameter('query', {"match_all": {}})
        response_all = es_m.search(apply_facts=False)

        total_counts = [bucket['doc_count'] for bucket in response_all['aggregations'][agg_type]['buckets']]
        relative_counts = [float(raw_counts[i])/total_counts[i] if total_counts[i] != 0 else 0 for i in range(len(total_counts))]
        return relative_counts,bucket_labels
    else:
        return raw_counts,bucket_labels
