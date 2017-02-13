""" Example script to create Facts form a given index and mapping

>> python facts_example.py MY_INDEX MY_MAPPING

"""
import json
import requests
import sys


def add_to_elasticsearch(data_str):
    base_url = r'http://127.0.0.1:9200/_bulk'
    response = requests.put(base_url, data=data_str)
    if response.status_code == 400:
        print '-- Not good... '
        print response.text


def get_simple_spans(corpus, fact_term):
    sentences = corpus.split('\n')
    global_index = 0
    spans = []
    for s in sentences:
        l = len(s) + 1
        s = s.lower()
        if fact_term in s:
            start = global_index
            end = global_index + l
            spans.append( (start, end) )
        global_index += l
    return spans


def main():

    _index = sys.argv[1]
    _type = sys.argv[2]

    print '- Creating facts for: {0}/{1}'.format(_index, _type)

    # Process FACTS
    field_path = ['document', 'text']
    fact_term = 'order'
    fact_name = 'doc_order'

    total_acc = 0
    query = json.dumps({u'query': {u'bool': {u'minimum_should_match': 0, u'should': [], u'must': []}}})
    request_url = 'http://localhost:9200/{0}/{1}/_search?search_type=scan&scroll=1m&size=100'.format(_index, _type)
    response = requests.post(request_url, data=query).json()
    scroll_id = response['_scroll_id']
    total_msg = response['hits']['total']
    total = total_msg

    data = []
    n_count = 0
    while total > 0:
        response = requests.post('http://localhost:9200/_search/scroll?scroll=1m', data=scroll_id).json()
        total = len(response['hits']['hits'])
        total_acc += total
        scroll_id = response['_scroll_id']
        # Wow, big bulk construction!
        for doc in response['hits']['hits']:
            n_count += 1
            doc_type = doc['_type']
            doc_id = doc['_id']
            doc_path = '.'.join(field_path)
            corpus_field = doc['_source']
            for sub_field in field_path:
                corpus_field = corpus_field[sub_field]
            spans = get_simple_spans(corpus_field, fact_term)
            if len(spans) == 0:
                continue
            spans_str = json.dumps(spans)
            document = {'facts': {'fact': fact_name,
                                  'spans': spans_str,
                                  'doc_id': doc_id,
                                  'doc_type': doc_type,
                                  'doc_path': doc_path}}
            index = {"index": {"_index": _index,
                               "_type": 'texta',
                               "_id": n_count}}
            index = json.dumps(index)
            document = json.dumps(document)
            data.extend([index, document])

    print 'Total of bulked facts: {0}'.format(len(data)/2)
    # Add all to elasticsearch
    data_str = '\n'.join(data)
    data_str += '\n'
    add_to_elasticsearch(data_str)
    print 'Done...'


if __name__ == '__main__':
    main()
