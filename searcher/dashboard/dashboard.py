import json
from pprint import pprint

import elasticsearch_dsl
from django.http import HttpRequest
from elasticsearch import Elasticsearch

from searcher.models import Search
from texta.settings import es_url
from utils.datasets import Datasets
from utils.es_manager import ES_Manager


class SearcherDashboard:

    def add_text_aggregations(self, field_name: str):
        pass

    def add_date_aggregations(self, field_name: str):
        bucket_name = field_name + '_bucket'
        self.search.aggs.bucket(bucket_name, 'date_histogram', field=field_name, interval="month")

    def add_number_aggregations(self, field_name: str):
        bucket_name = field_name + '_bucket'
        self.search.aggs.bucket(bucket_name, 'stats', field=field_name)

    def add_keyword_aggregations(self, field_name: str):
        bucket_name = field_name + '_bucket'
        self.search.aggs.bucket(bucket_name, 'terms', field=field_name, size=100)

    def apply_aggregations_to_fields(self):
        for field_dict in self.fields_with_schemas:
            field_name, field_type = field_dict.get('field'), field_dict.get('type')
            self.aggregation_mapping[field_type](field_name)

    def __init__(self, request: HttpRequest, elasticsearch_manager: ES_Manager, search_model_pk: int):
        self.aggregation_mapping = {
            'float': self.add_number_aggregations,
            'long': self.add_number_aggregations,
            'integer': self.add_number_aggregations,
            'double': self.add_number_aggregations,
            'date': self.add_date_aggregations,

            'text': self.add_text_aggregations,
            'keyword': self.add_keyword_aggregations,

            # WIP
            'array': self.add_number_aggregations,
            'object': self.add_number_aggregations,
            'nested': self.add_number_aggregations,

        }
        self.es_manager = elasticsearch_manager
        self.ds = Datasets().activate_datasets(request.session)  # Gives access to all the active datasets names.
        self.query = json.loads(Search.objects.get(id=search_model_pk).query)  # Contains main query and facts query.

        # Index parameter contains comma delimited string for multi-index support.
        self.search = elasticsearch_dsl.Search(using=Elasticsearch(es_url), index=self.es_manager.stringify_datasets()).update_from_dict(self.query.get('main'))
        self.fields_with_schemas = self.es_manager.get_fields_and_schemas(remove_duplicate_keys=True)

        self.apply_aggregations_to_fields()
        self.response = self.search.execute()

        self.json_response = self.response.to_dict()

        self.document_count = self.es_manager.get_document_count(self.query['main'])
