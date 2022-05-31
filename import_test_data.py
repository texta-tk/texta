#!/usr/bin/env python
import argparse
import json
import zipfile
from io import BytesIO
from urllib.request import urlopen

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

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
    help='The final index name of the testing index that will be added to Elasticsearch. If an old index exists, IT WILL BE DELETED!'
)
parser.add_argument(
    '-ei',
    type=str,
    default='texta_test_index_evaluator',
    help='The final index name of the evaluation testing index that will be added to Elasticsearch. If an old index exists, IT WILL BE DELETED!'
)
parser.add_argument(
    '-vi',
    type=str,
    default='texta_test_index_entity_evaluator',
    help='The final index name of the entity evaluation testing index that will be added to Elasticsearch. If an old index exists, IT WILL BE DELETED!'
)
parser.add_argument(
    '-ci',
    type=str,
    default='texta_crf_test_index',
    help='The final index name of the evaluation testing index that will be added to Elasticsearch. If an old index exists, IT WILL BE DELETED!'
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
    "crf": {
        "index": args.ci,
        "url": url_prefix + "elastic_data/texta_crf_test_index.zip",
        "file_name": "texta_crf_test_index"
    },
    "ev": {
        "index": args.ei,
        "url": url_prefix + "elastic_data/texta_test_index_evaluator.zip",
        "file_name": "texta_test_index_evaluator"
    },
    "eev": {
        "index": args.vi,
        "url": url_prefix + "elastic_data/texta_test_index_entity_evaluator.zip",
        "file_name": "texta_test_index_entity_evaluator"
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
                'str_val': {'type': 'keyword'},
                'sent_index': {'type': 'long'},
                'id': {'type': 'keyword'},
                'source': {'type': 'keyword'}
            }
        }
    }
}


def actions_generator(fp, index_name):
    for line in fp:
        line = line.strip()
        if line:
            document = json.loads(line)
            yield {
                "_index": index_name,
                "_type": "_doc",
                "_source": document,
                "retry_on_conflict": 3
            }


def import_docs(params):
    print("Downloading test data.")
    response = urlopen(params["url"])
    test_data_zip = BytesIO(response.read())
    print("Reading test data.")
    with zipfile.ZipFile(test_data_zip) as z:
        with z.open(params["file_name"] + '.jl') as f:
            print("Deleting existing index for safety precaution.")
            indices = params["index"].split(",")
            for index in indices:
                es.indices.delete(index=index, ignore=[400, 404])
                es.indices.create(index=index, body={'mappings': FACT_MAPPING})
                print(f"Created index {index} with fact mappings.")
                print("Line-per-line data insertion, this might take a moment...")
                actions = actions_generator(f, index)
                bulk(client=es, actions=actions, refresh="wait_for")
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
        print("Processing binary/multilabel evaluator dataset:")
        import_docs(dataset_params["ev"])
        print("Processing entity evaluator dataset:")
        import_docs(dataset_params["eev"])
        print("Processing CRF dataset")
        import_docs(dataset_params["crf"])
        if LARGE is True:
            print("Processing large dataset:")
            import_docs(dataset_params["lg"])
        import_collections(dataset_params["collection"])
    except Exception as e:
        print(e)
        print('An error occurred during loading and importing the data')


if __name__ == "__main__":
    main()
