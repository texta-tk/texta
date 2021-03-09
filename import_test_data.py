#!/usr/bin/env python
import argparse
import json
import zipfile
from io import BytesIO
from urllib.request import urlopen

from elasticsearch import Elasticsearch

from toolkit.settings import CORE_SETTINGS, TEST_DATA_DIR


ES_URL = CORE_SETTINGS["TEXTA_ES_URL"]
ES_USERNAME = CORE_SETTINGS["TEXTA_ES_USERNAME"]
ES_PASSWORD = CORE_SETTINGS["TEXTA_ES_PASSWORD"]

parser = argparse.ArgumentParser(description='Import the Elasticsearch index for unit tests.')
parser.add_argument(
    '-es',
    type=str,
    default=ES_URL,
    help='Elasticsearch host URL, default: localhost:9200'
)
parser.add_argument(
    '-i',
    type=str,
    default='texta_test_index,texta_test_index_mlp',
    help='The final index name of the testing index, that will be added to Elasticsearch. If an old index exists, IT WILL BE DELETED!'
)
parser.add_argument(
    '-lg',
    type=bool,
    default=False,
    help='Also import larger dataset for performance testing.'
)

args = parser.parse_args()

HOST = args.es
LARGE = args.lg

url_prefix = "https://git.texta.ee/texta/texta-resources/raw/master/tk_test_data/"

dataset_params = {
    "lg": {
        "index": args.i + "_large",
        "url": url_prefix + "elastic_data/texta_test_index_large.zip",
        "file_name": "texta_test_index_large"
    },
    "sm": {
        "index": args.i,
        "url": url_prefix + "elastic_data/texta_test_index.zip",
        "file_name": "texta_test_index"
    },
    "collection": {
        "url": url_prefix + "import_data/import_test_data.zip"
    }
}

es = Elasticsearch(HOST, http_auth=(ES_USERNAME, ES_PASSWORD))

FACT_MAPPING = {
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


def import_docs(params):
    print("Downloading test data.")
    response = urlopen(params["url"])
    test_data_zip = BytesIO(response.read())
    print("Reading test data.")
    with zipfile.ZipFile(test_data_zip) as z:
        with z.open(params["file_name"] + '.jl') as f:
            lines = f.readlines()
    if not lines:
        print("Failed reading test data.")
    else:
        print("Deleting existing index for safety precaution.")
        indices = params["index"].split(",")
        for index in indices:
            es.indices.delete(index=index, ignore=[400, 404])
            es.indices.create(index=index, body={'mappings': FACT_MAPPING})
            print(f"Created index {index} with fact mappings.")
            print(f"Line-per-line data insertion into ES {ES_URL}, this might take a moment...")
            for line in lines:
                line = line.strip()
                if line:
                    doc = json.dumps(json.loads(line))
                    es.index(index=index, body=doc)
            print('Test Elasticsearch index imported successfully')
            print('')


def import_collections(params):
    print("Downloading test collections.")
    response = urlopen(params["url"])
    test_data_zip = BytesIO(response.read())
    print("Reading test collections.")
    with zipfile.ZipFile(test_data_zip) as z:
        z.extractall(TEST_DATA_DIR)
    print("Extracted test collections.")


def main():
    try:
        print("Processing small dataset:")
        import_docs(dataset_params["sm"])
        if LARGE is True:
            print("Processing large dataset:")
            import_docs(dataset_params["lg"])
        import_collections(dataset_params["collection"])
    except Exception as e:
        print(e)
        print('An error occurred during loading and importing the data')


if __name__ == "__main__":
    main()
