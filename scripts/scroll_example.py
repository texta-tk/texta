# -*- coding: utf8 -*-
import requests
import json

es_url = 'http://localhost:9200'

dataset = ''
mapping = ''

query = {
    "query" : {
        "match" : {"lahendi_liik":"kohtuotsus"}
        }
    }

response = requests.post(es_url+'/'+dataset+'/'+mapping+'/_search?search_type=scan&scroll=1m&size=500',data=json.dumps(query)).json()

scroll_id = response['_scroll_id']
l = response['hits']['total']

while l > 0:
    response = requests.post(es_url+'/_search/scroll?scroll=1m',data=scroll_id).json()
    l = len(response['hits']['hits'])
    scroll_id = response['_scroll_id']
    for hit in response['hits']['hits']:
        # do something here
        pass
