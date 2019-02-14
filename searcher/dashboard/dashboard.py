import elasticsearch

from searcher.dashboard.formaters.multi_search_formater import MultiSearchFormater
from searcher.dashboard.formaters.single_search_formater import SingleSearchFormater
from searcher.dashboard.query_conductors.multi_search_conductor import MultiSearchConductor
from searcher.dashboard.query_conductors.single_search_conductor import SingleSearchConductor


class MultiSearcherDashboard:

    def __init__(self, es_url: str, indices: str, query_body: dict = None, excluded_fields: list = None):
        self.indices = indices
        self.es_url = es_url
        self.excluded_fields = ['_texta_id', '_texta_id.keyword'] + excluded_fields if isinstance(excluded_fields, list) else ['_texta_id', '_texta_id.keyword']
        self.query_body = query_body
        self.elasticsearch = elasticsearch.Elasticsearch(self.es_url, timeout=120, )
        self.field_counts = {}

    def conduct_query(self):
        conductor = MultiSearchConductor()
        result = conductor.query_conductor(self.indices, query_body=self.query_body, elasticsearch=self.elasticsearch, es_url=self.es_url, excluded_fields=self.excluded_fields)
        self.field_counts = conductor.field_counts
        return result

    def format_result(self, response):
        formater = MultiSearchFormater()
        result = formater.format_result(response=response, field_counts=self.field_counts)
        return result


class SingleSearcherDashboard:

    def __init__(self, es_url: str, indices: str, query_body: dict = None, excluded_fields: list = None):
        self.indices = indices
        self.es_url = es_url
        self.excluded_fields = ['_texta_id', '_texta_id.keyword'] + excluded_fields if isinstance(excluded_fields, list) else ['_texta_id', '_texta_id.keyword']
        self.query_body = query_body
        self.elasticsearch = elasticsearch.Elasticsearch(self.es_url, timeout=120, )

    def conduct_query(self):
        conductor = SingleSearchConductor()
        result = conductor.query_conductor(self.indices, query_body=self.query_body, elasticsearch=self.elasticsearch, es_url=self.es_url, excluded_fields=self.excluded_fields)
        return result

    def format_result(self, response):
        formater = SingleSearchFormater()
        result = formater.format_result(response=response)
        return result
