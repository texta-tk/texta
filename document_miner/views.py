# -*- coding: utf8 -*-

import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
import requests

from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from corpus_tool.models import Search
from permission_admin.models import Dataset

from texta.settings import STATIC_URL, URL_PREFIX, es_url


@login_required
def get_saved_searches(request):  
    searches = Search.objects.filter(author=request.user).filter(dataset=Dataset(pk=int(request.session['dataset'])))
    return HttpResponse(json.dumps([{'id':search.pk,'desc':search.description} for search in searches],ensure_ascii=False))


@login_required
def index(request):
    template = loader.get_template('document_miner.html')
    request.session['seen_docs'] = []

    # Define selected mapping
    ds = Datasets().activate_dataset(request.session)
    dataset = ds.get_index()
    mapping = ds.get_mapping()

    # Get field names and types
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    fields = es_m.get_column_names()
    
    return HttpResponse(template.render({'STATIC_URL':STATIC_URL,'fields':fields},request))

def add_documents(ids,index,mapping):
    out = []
    for id in ids:
        out.append({"_index" : index, "_type" : mapping, "_id" : id})
    return out


def get_docs_from_searches(request):
    document_ids = {}
    searches = [x for x in request.POST.keys() if x.startswith('saved_search')]

    for search in searches:
        search_id = request.POST[search]
        s = json.loads(Search.objects.get(pk=search_id).query)

        ds = Datasets().activate_dataset(request.session)
        es_m = ds.build_manager(ES_Manager)

        es_m.load_combined_query(s)

        # Scroll the results
        response = es_m.scroll(id_scroll=True)
        scroll_id = response['_scroll_id']
        hits = response['hits']['hits']

        while hits:
            hits = response['hits']['hits']
            for hit in hits:
                document_ids[hit['_id']] = True
            response = es_m.scroll(scroll_id=scroll_id)
            scroll_id = response['_scroll_id']

    return document_ids.keys()


@login_required
def query(request):
    
    out = []
    field = request.POST['field']

    docs_from_searches = get_docs_from_searches(request)

    # Define selected mapping
    ds = Datasets().activate_dataset(request.session)
    dataset = ds.get_index()
    mapping = ds.get_mapping()

    handle_negatives = request.POST['handle_negatives']
    ids = [a.strip() for a in request.POST['docs'].split('\n') if a]
    docs_declined = json.loads(request.POST['docs_declined'])

    stopwords = [a.strip() for a in request.POST['stopwords'].split('\n')]

    # Merge ids
    ids = ids+docs_from_searches

    mlt = {
        "more_like_this": {
            "fields" : [field],
            "like" : add_documents(ids,dataset,mapping),
            "min_term_freq" : 1,
            "max_query_terms" : 12,
        }
    }

    if stopwords:
        mlt["more_like_this"]["stop_words"] = stopwords

    query = {
        "query":{
            "bool":{
                "must":[mlt]
            }
        },
        "size":20,
        "highlight" : {
            "pre_tags" : ["<b>"],
            "post_tags" : ["</b>"],
            "fields" : {
                field : {}
            }
        }
    }

    if handle_negatives == 'unlike':
        mlt["more_like_this"]["unlike"] = add_documents(docs_declined,dataset,mapping)
    else:
        if docs_declined:
            declined = [{'ids':{'values':docs_declined}}]
            query["query"]["bool"]["must_not"] = declined

    response = ES_Manager.plain_search(es_url, dataset, mapping, query)

    for hit in response['hits']['hits']:
        field_content = get_field_content(hit,field)
        row = '''
                    <tr id="row_'''+hit['_id']+'''">
                        <td><a href="javascript:accept_document('''+hit['_id']+''')">Accept</a></td>
                        <td><a href="javascript:decline_document('''+hit['_id']+''')">Reject</a></td>
                        <td>'''+hit['_id']+'''</td>
                        <td>'''+field_content+'''</td>
                    </tr>
        '''
        out.append(row)

    if not out:
        out.append('No matches from supported IDs.')

    return HttpResponse('<table class="table">'+''.join(out)+'</table>')


def get_field_content(hit,field):

    #TODO Highlight

    field_content = hit['_source']
    for field_element in field.split('.'):
        field_content = field_content[field_element]

    return field_content
    
