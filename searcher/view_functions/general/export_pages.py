import json
import csv
from collections import Counter
from django.http import HttpResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from searcher.view_functions.general.searcher_utils import improve_facts_readability

try:
    from io import StringIO 
except:
    from io import BytesIO 

ES_SCROLL_BATCH = 100


@login_required
def export_pages(request):

    es_params = request.session.get('export_args')
    if es_params is not None:
        if es_params['num_examples'] == '*':
            response = StreamingHttpResponse(get_all_rows(es_params, request), content_type='text/csv')
        else:
            response = StreamingHttpResponse(get_rows(es_params, request), content_type='text/csv')

        response['Content-Disposition'] = 'attachment; filename="%s"' % (es_params['filename'])

        return response

    logger = LogManager(__name__, 'SEARCH CORPUS')
    logger.set_context('user_name', request.user.username)
    logger.error('export pages failed, parameters empty')
    return HttpResponse()

def get_rows(es_params, request):
    try:
        buffer_ = StringIO()
    except:
        buffer_ = BytesIO()

    writer = csv.writer(buffer_)

    features = es_params['features']
    writer.writerow(features) 

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    es_m.set_query_parameter('from', es_params['examples_start'])
    q_size = es_params['num_examples'] if es_params['num_examples'] <= ES_SCROLL_BATCH else ES_SCROLL_BATCH
    es_m.set_query_parameter('size', q_size)

    response = es_m.scroll()
    scroll_id = response['_scroll_id']
    left = es_params['num_examples']
    hits = response['hits']['hits']

    while hits and left:
        rows = process_hits(hits, features, write=False)

        if left > len(rows):
            for row in rows:
                writer.writerow(row)
            yield _get_buffer_data(buffer_)

            left -= len(rows)
            response = es_m.scroll(scroll_id=scroll_id)
            hits = response['hits']['hits']
            scroll_id = response['_scroll_id']

        elif left == len(rows):
            for row in rows:
                writer.writerow(row)
            yield _get_buffer_data(buffer_)
            break
        else:
            for row in rows[:left]:
                writer.writerow(row)
            yield _get_buffer_data(buffer_)
            break


def get_all_rows(es_params, request):
    features = es_params['features']

    # Prepare in-memory csv writer.
    buffer_ = StringIO()
    writer = csv.writer(buffer_)

    # Write the first headers.
    writer.writerow(features)

    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    es_m.set_query_parameter('size', ES_SCROLL_BATCH)

    # Fetch the initial scroll results.
    response = es_m.scroll()
    scroll_id = response['_scroll_id']
    hits = response['hits']['hits']

    while hits:
        process_hits(hits, features, write=True, writer=writer)
        # Return some data with the StreamingResponce
        yield _get_buffer_data(buffer_)

        # Continue with the scroll.
        response = es_m.scroll(scroll_id=scroll_id)
        hits = response['hits']['hits']
        scroll_id = response['_scroll_id']


def process_hits(hits, features, write=True, writer=None):
    """
    Loops over hits and process them.
    In the end either write with a csvwriter or append to an array.
    write - bool: True to write with csvwriter, False, to append to an array
    """
    if not write:
        rows = []

    for hit in hits:
        row = []
        for feature_name in features:
            document_content = hit['_source']
            # Some features like mlp.lemmas are dot, separated.
            for sub_field in feature_name.split('.'):
                if sub_field in document_content:
                    document_content = document_content[sub_field]
                else:
                    document_content = ""
                    break

            if feature_name == 'texta_facts':
                content = improve_facts_readability(document_content, join_with=' - ', indent_with='')
                # Append JSON format
                content = '{}     {}'.format(content, document_content) 
            else:
                # stringify just in case value is something like a bool
                document_content = str(document_content)
                # Escape newlines and double quotes that break the csv
                content = document_content.replace('\n', ' \\n').replace('"', '\"')
            row.append(content)
        if not write:
            rows.append(row)
        elif write:
            writer.writerow(row)

    # If write, no need to return the writer
    if not write:
        return rows


def _get_buffer_data(buffer_):
    buffer_.seek(0)
    data = buffer_.read()
    buffer_.seek(0)
    buffer_.truncate()
    return data
