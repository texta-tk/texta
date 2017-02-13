import requests
import json
import csv
import sys, os
from zipfile import ZipFile

sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, 'texta','utils'))) # Add texta.utils temporarily to allow es_manager import 
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))) # Add .. temporarily to allow TEXTA settings import through es_manager

from es_manager import ES_Manager
from settings import es_url

# Remove temporary paths to avoid future conflicts
sys.path.pop()
sys.path.pop()

os.chdir(os.path.realpath(os.path.dirname(__file__)))

index = "journal"
mapping = "articles"

bulk_size = 200
id_field = 'id'

#es_url = 'http://127.0.0.1:9200'

def transform_document(doc_dict):
    new_doc_dict = doc_dict
    content = doc_dict['content']
    lemmas = doc_dict['lemmas']
    
    del new_doc_dict['content']
    del new_doc_dict['lemmas']
    
    new_doc_dict['content'] = {'text':content, 'lemmas':lemmas}
    
    return new_doc_dict

ES_Manager.plain_delete(es_url+'/'+index)
ES_Manager.plain_put(es_url+'/'+index, data=json.dumps({'mappings':{mapping:{},'facts':{}}}))

with ZipFile('data.zip','r') as zip_file:
    with zip_file.open('data.csv') as fin:
        reader = csv.DictReader(fin)

        data = []

        counter = 0

        for row in reader:
            counter += 1
            
            doc = transform_document(row)
            
            data.append(json.dumps({"index":{"_index":index,"_type":mapping,"_id":row['id']}}))
            data.append(json.dumps(doc))

            if counter == bulk_size:
                response = ES_Manager.plain_put(es_url+'/'+index+'/'+mapping+'/_bulk', data='\n'.join(data))
                counter = 0
                data = []
                        
        if data:
            response = ES_Manager.plain_put(es_url+'/'+index+'/'+mapping+'/_bulk', data='\n'.join(data))