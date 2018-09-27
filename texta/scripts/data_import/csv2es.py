### Example script for importing CSV contents into Elasticsearch

import csv
from datetime import datetime
from django.utils.encoding import smart_str
import requests
from estnltk import Text
import json
from time import time

def lemmatise(txt):
    out = []
    txt = Text(txt.decode('latin1').encode('utf8'))
    txt.analysis
    for sent in txt.divide():
        out.append(' '.join([word['analysis'][0]['lemma'].lower() for word in sent]))
    return '\n'.join(out)

ignore_fields = ['case_length','debt_balances','max_days_due','lab_tax_lq','exp_payment','tax_debt','state_tax_lq','tax_declar']
to_be_lemmatised = ['event_description']
id_field = 'id'
bulk_size = 1000

index_name   = 'inforegister'
mapping_name = 'cases'

with open('cases.csv','r') as fh:
    reader = csv.reader(fh)
    column_names = []
    data = ''
    i=0
    j=0
    for row in reader:
        if i==0:
            column_names = row
        else:
            j+=1
            out_dict = {}
            for k,column in enumerate(row):
                if column_names[k] not in ignore_fields:
                    if column_names[k] in to_be_lemmatised:
                        out_dict[column_names[k]+'_lemmas'] = lemmatise(column)
                    out_dict[column_names[k]] = column.decode('latin1').encode('utf8')
            data += json.dumps({"index":{"_index":index_name,"_type":mapping_name,"_id":str(j)}})+'\n'
            data += json.dumps(out_dict)+'\n'
            if i == bulk_size:
                i=0
                response = requests.put('http://127.0.0.1:9200/'+index_name+'/'+mapping_name+'/_bulk', data=data)
                print datetime.now(),'Bulk indexed. HTTP says:',response.status_code
                if response.status_code == 400:
                    print response.text
                data = ''
        i+=1

    response = requests.put('http://127.0.0.1:9200/'+index_name+'/'+mapping_name+'/_bulk', data=data)
    print datetime.now(),'Bulk indexed. HTTP says:',response.status_code
    if response.status_code == 400:
        print response.text
    print 'All indexed.'

