import json
import csv
from collections import Counter
from django.http import HttpResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

try:
    from io import StringIO  # NEW PY REQUIREMENT
except:
    from io import BytesIO  # NEW PY REQUIREMENT

ES_SCROLL_BATCH = 100


@login_required
def export_pages(request):
    es_params = {entry['name']: entry['value'] for entry in json.loads(request.GET['args'], encoding='utf8')}

    if es_params['num_examples'] == '*':
        response = StreamingHttpResponse(get_all_rows(es_params, request), content_type='text/csv')
    else:
        response = StreamingHttpResponse(get_rows(es_params, request), content_type='text/csv')

    response['Content-Disposition'] = 'attachment; filename="%s"' % (es_params['filename'])

    return response


def get_rows(es_params, request):
    try:
        buffer_ = StringIO()
    except:
        buffer_ = BytesIO()

    writer = csv.writer(buffer_)

    try:
        writer.writerow(es_params['features'])  # NEW PY REQUIREMENT
    except:
        writer.writerow([feature for feature in es_params['features']])

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)

    es_m.set_query_parameter('from', es_params['examples_start'])
    q_size = es_params['num_examples'] if es_params['num_examples'] <= ES_SCROLL_BATCH else ES_SCROLL_BATCH
    es_m.set_query_parameter('size', q_size)

    features = sorted(es_params['features'])

    response = es_m.scroll()

    scroll_id = response['_scroll_id']
    left = es_params['num_examples']
    hits = response['hits']['hits']

    while hits and left:
        rows = process_hits(hits, features, write=False)

        if left > len(rows):
            for row in rows:
                writer.writerow([element if isinstance(element, str) else element for element in row])
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
                writer.writerow([element if isinstance(element, str) else element for element in row])
            buffer_.seek(0)
            data = buffer_.read()
            buffer_.seek(0)
            buffer_.truncate()
            yield data

            break
        else:
            for row in rows[:left]:
                writer.writerow([element if isinstance(element, str) else element for element in row])
            buffer_.seek(0)
            data = buffer_.read()
            buffer_.seek(0)
            buffer_.truncate()
            yield data

            break


def get_all_rows(es_params, request):
    features = sorted(es_params['features'])

    # Prepare in-memory csv writer.
    buffer_ = StringIO()
    writer = csv.writer(buffer_)

    # Write the first headers.
    writer.writerow([feature for feature in es_params['features']])

    # Prepare Elasticsearch for the scroll.
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    es_m.build(es_params)
    es_m.set_query_parameter('size', ES_SCROLL_BATCH)

    # Fetch the initial scroll results.
    response = es_m.scroll()
    scroll_id = response['_scroll_id']
    hits = response['hits']['hits']

    while hits:
        process_hits(hits, features, write=True, writer=writer)

        buffer_.seek(0)
        data = buffer_.read()
        buffer_.seek(0)
        buffer_.truncate()
        yield data  # Return some data with the StreamingResponce

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

            # Some features like mlp.lemmas are dot, separated.
            feature_path = feature_name.split('.')
            document_content = hit['_source']

            for path_component in feature_path:
                if path_component in document_content:
                    document_content = document_content[path_component]
                else:
                    document_content = ""
                    break

            if feature_name == u'texta_facts':
                content = []
                facts = ['{ "' + x["fact"] + '": "' + x["str_val"] + '"}' for x in sorted(document_content, key=lambda k: k['fact'])]
                fact_counts = Counter(facts)

                facts = list(set(facts))
                facts_dict = []
                for fact in facts:
                    try:
                        facts_dict.append(json.loads(fact, encoding='utf8'))
                    except json.decoder.JSONDecodeError as e:
                        facts_dict.append({'system_message': "Faulty content"})

                for index, dictionary in enumerate(facts_dict):

                    for dict_key in dictionary:
                        if dict_key not in content:
                            content.append(dict_key)
                        content.append('{}: {}'.format(dictionary[dict_key], fact_counts[facts[index]]))

                content = ' - '.join(content)
                content = '{}; {}'.format(content, document_content)  # Append JSON format
            else:
                content = document_content.replace('\n', '\\n').replace('"', '\"') if isinstance(document_content, str) else document_content

            row.append(content)
        if not write:
            rows.append(row)
        elif write:
            writer.writerow([element if isinstance(element, str) else element for element in row])

    # If write, no need to return the writer
    if not write:
        return rows
