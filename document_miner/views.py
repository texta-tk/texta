# -*- coding: utf8 -*-
from settings import STATIC_URL, URL_PREFIX, es_url
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from utils.datasets import get_datasets
import requests
import json

@login_required
def index(request):
    template = loader.get_template('document_miner/index.html')
    request.session['seen_docs'] = []

    # Define selected mapping
    datasets = get_datasets()
    selected_mapping = int(request.session['dataset'])
    dataset = datasets[selected_mapping]['index']
    mapping = datasets[selected_mapping]['mapping']

    # Get field names and types
    fields = sorted(requests.get(es_url+'/'+dataset).json()[dataset]['mappings'][mapping]['properties'])
    fields = sorted(fields)
    
    return HttpResponse(template.render({'STATIC_URL':STATIC_URL,'fields':fields},request))

def add_documents(ids,index,mapping):
    out = []
    for id in ids:
        out.append({"_index" : index, "_type" : mapping, "_id" : id})
    return out

@login_required
def query(request):
    out = []
    field = request.POST['field']

    # Define selected mapping
    datasets = get_datasets()
    selected_mapping = int(request.session['dataset'])
    dataset = datasets[selected_mapping]['index']
    mapping = datasets[selected_mapping]['mapping']
    
    handle_negatives = request.POST['handle_negatives']
    ids = [a.strip() for a in request.POST['docs'].split('\n')]
    docs_declined = json.loads(request.POST['docs_declined'])

    stopwords = [a.strip() for a in request.POST['stopwords'].split('\n')]

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

    print query

    response = requests.post(es_url+'/'+dataset+'/'+mapping+'/_search',data=json.dumps(query)).json()
    
    try:
        for hit in response['hits']['hits']:
            try:
                row = '''
                    <tr id="row_'''+hit['_id']+'''">
                        <td><a not_yet_accepted="'''+hit['_id']+'''" href="javascript:accept_document('''+hit['_id']+''')">Accept</a></td>
                        <td>'''+hit['_id']+'''</td>
                        <td>'''+'\n'.join(hit['highlight'][field])+'''</td>
                    </tr>
                '''
            except KeyError:
                row = '''
                    <tr id="row_'''+hit['_id']+'''">
                        <td><a href="javascript:accept_document('''+hit['_id']+''')">Accept</a></td>
                        <td><a href="javascript:decline_document('''+hit['_id']+''')">Reject</a></td>
                        <td>'''+hit['_id']+'''</td>
                        <td>'''+hit['_source'][field]+'''</td>
                    </tr>
                '''            
            out.append(row)
    except:
        KeyError

    if not out:
        out.append('No matches from supported IDs.')

    return HttpResponse('<table class="table">'+''.join(out)+'</table>')

