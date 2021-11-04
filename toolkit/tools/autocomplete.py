from toolkit.core.lexicon.models import Lexicon
from texta_elastic.searcher import ElasticSearcher


class Autocomplete:

    def __init__(self, project, indices, limit = 10):
        self.project = project
        self.limit = limit
        self.es = ElasticSearcher(output=ElasticSearcher.OUT_RAW, indices=indices)

    def get_fact_names(self, startswith):
        query = {"aggs": {'fact': {"nested": {"path": "texta_facts"}, "aggs": {'fact': {"terms": {"field": "texta_facts.fact", "size": self.limit, "include": f"{startswith}.*"}}}}}}

        self.es.update_query(query)
        results = self.es.search()

        facts = [a['key'] for a in results['aggregations']['fact']['fact']['buckets']]

        return facts


    def get_fact_values(self, startswith, fact_name):
        query = {"aggs": {'str_val': {"nested": {"path": "texta_facts"}, "aggs": {'str_val': {"terms": {"field": "texta_facts.fact"}, "aggs": {"fact_values": {"terms": {"field": "texta_facts.str_val", "size": self.limit, "include": f"{startswith}.*"}}}}}}}}

        self.es.update_query(query)
        results = self.es.search()

        facts = []
        for bucket in results['aggregations']['str_val']['str_val']['buckets']:
            if bucket['key'] == fact_name:
                facts += [sub_bucket['key'] for sub_bucket in bucket['fact_values']['buckets']]

        return facts

    def get_lexicons(self, startswith):
        # TODO
        pass
