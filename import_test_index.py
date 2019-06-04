import json
import argparse
import zipfile
from elasticsearch import Elasticsearch

parser = argparse.ArgumentParser(description='Import the Elasticsearch index for unit tests.')
parser.add_argument('-es', type=str, default='localhost:9200',
                   help='Elasticsearch host URL, default: localhost:9200')
parser.add_argument('-f', type=str, default='texta_test_index',
                   help='The JSON-lines (.jl) file, name, and also the .zip container containing it, from where to import the data. Zipfile must be in the "data/test_data/" folder. default: texta_test_index')
parser.add_argument('-i', type=str, default='texta_test_index',
                   help='The final index name of the testing index, that will be added to Elasticsearch')

args = parser.parse_args()

file_name = args.f
host = args.es
index = args.i

es = Elasticsearch()

def import_docs():
    try:
        with zipfile.ZipFile(f'data/test_data/{file_name}.zip', 'r') as z:
            with z.open(f'{file_name}.jl') as f:
                lines = f.readlines()
                for line in lines:
                    doc = json.dumps(json.loads(line)['_source'])
                    es.index(index=index, body=doc, doc_type='test')
        print('Test Elasticsearch index imported successfully')
    except Exception as e:
        print(e)
        print('An error occurred during loading and importing the data')
    

import_docs()
