# -*- coding: utf8 -*-

### Example script for importing data from MySQL

from django.utils.encoding import smart_str
from datetime import datetime
from time import time
import MySQLdb
import MySQLdb.cursors 
import requests
import json

ignore_fields = ['json']
id_field = 'id'

index_name   = 'etsa'
mapping_name = 'mir'

db=MySQLdb.connect(host        = 'localhost',
                   port        = 3306,
                   user        = '',
                   passwd      = '',
                   db          = 'work',
                   charset     = 'utf8',
                   use_unicode = True,
                   cursorclass=MySQLdb.cursors.SSDictCursor)
cur = db.cursor()
cur.execute('select * from mir_events')
print datetime.now(),'MySQL query executed.'

i = 0
data = ''
bulk_size = 1000
algus = time()

for row in cur:
    out_dict = {}
    for column in row:
        if column not in ignore_fields:
            out_dict[column] = smart_str(row[column])
    data += json.dumps({"index":{"_index":index_name,"_type":mapping_name,"_id":str(row[id_field])}})+'\n'
    data += json.dumps(out_dict)+'\n'
    i+=1
    if i == bulk_size:
        i=0
        response = requests.put('http://127.0.0.1:9200/'+index_name+'/'+mapping_name+'/_bulk', data=data)
        print datetime.now(),'Bulk indexed. HTTP says:',response.status_code
        if response.status_code == 400:
            print response.text
        data = ''

response = requests.put('http://127.0.0.1:9200/'+index_name+'/'+mapping_name+'/_bulk', data=data)
print datetime.now(),'Bulk indexed. HTTP says:',response.status_code
if response.status_code == 400:
    print response.text
print 'All indexed.',time()-algus
