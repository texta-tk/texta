import json
import argparse
import zipfile
from urllib.request import urlopen
from io import BytesIO
from elasticsearch import Elasticsearch

from toolkit.settings import ES_PASSWORD, ES_USERNAME

parser = argparse.ArgumentParser(description='Import the Elasticsearch index for unit tests.')
parser.add_argument('-es', type=str, default='localhost:9200',
                   help='Elasticsearch host URL, default: localhost:9200')
parser.add_argument('-f', type=str, default='texta_test_index',
                   help='The JSON-lines (.jl) file, name, and also the .zip container containing it, from where to import the data. Zipfile must be in the "data/test_data/" folder. default: texta_test_index')
parser.add_argument('-i', type=str, default='texta_test_index',
                   help='The final index name of the testing index, that will be added to Elasticsearch. If an old index exists, IT WILL BE DELETED!')

args = parser.parse_args()

file_name = args.f
host = args.es
index = args.i

test_data_url = "https://git.texta.ee/texta/texta-resources/raw/master/tk_test_data/texta_test_index.zip"

es = Elasticsearch(host, http_auth=(ES_USERNAME, ES_PASSWORD))

fact_mapping = {
    'test_mapping': {
        'properties': {
            'texta_facts': {
                'type': 'nested',
                'properties': {
                    'doc_path': {'type': 'keyword'},
                    'fact': {'type': 'keyword'},
                    'num_val': {'type': 'long'},
                    'spans': {'type': 'keyword'},
                    'str_val': {'type': 'keyword'}
                }
            }
        }
    }
}


def import_docs():
    try:
        print("Downloading test data.")
        response = urlopen(test_data_url)
        test_data_zip = BytesIO(response.read())
        print("Reading test data.")
        with zipfile.ZipFile(test_data_zip) as z:
            with z.open(f'{file_name}.jl') as f:
                lines = f.readlines()
                print("Deleting existing index for safety precaution.")
                es.indices.delete(index=index, ignore=[400, 404])
                es.indices.create(index=index, body={'mappings': fact_mapping})
                print("Created new index with fact mappings.")

                print("Line-per-line data insertion, this might take a moment...")
                for line in lines:
                    doc = json.dumps(json.loads(line))
                    es.index(index=index, body=doc, doc_type='test_mapping')
        print('Test Elasticsearch index imported successfully')
    except Exception as e:
        print(e)
        print('An error occurred during loading and importing the data')
    

import_docs()
