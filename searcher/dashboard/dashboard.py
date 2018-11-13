import json
import time
from pprint import pprint

import elasticsearch_dsl
from django.http import HttpRequest
from elasticsearch import Elasticsearch

from searcher.models import Search
from texta.settings import es_url
from utils.datasets import Datasets
from utils.es_manager import ES_Manager


class SearcherDashboard:

    def __init__(self, indices: str, normal_fields, nested_fields, search_model_pk: int = None):
        self.indices = indices
        self.normal_fields = normal_fields
        self.nested_fields = nested_fields

        self.field_to_aggregation_mapping = {
            'keyword': 'terms',
            'date': 'date_histogram',
            'long': 'stats',
            'integer': 'stats',
            'float': 'stats',
        }

        # Index parameter contains comma delimited string for multi-index support.
        self.search = elasticsearch_dsl.Search(using=Elasticsearch(es_url), index=self.indices).params(typed_keys=True)
        self.response = self.search.execute()
