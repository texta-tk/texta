from utils.datasets import Datasets
from utils.es_manager import ES_Manager
import json

class FactManager:
    """ Manage Searcher facts, like deleting/storing, adding facts.
    """
    def __init__(self,request):
        self.key = list(request.POST.keys())[0]
        self.val = request.POST[self.key]

        ds = Datasets().activate_dataset(request.session)
        self.dataset = ds.get_index()
        self.mapping = ds.get_mapping()
        self.es_m = ES_Manager(self.dataset, self.mapping)
        self.field = 'texta_facts'

    def remove_facts_from_document(self, bs=7500):
        self.es_m.clear_readonly_block()
        query = {"main": {"query": {"nested":
            {"path": self.field,"query": {"bool": {"must":
            [{ "match": {self.field + ".fact": self.key }},
            { "match": {self.field + ".str_val":  self.val }}]}}}},
            "_source": [self.field]}}

        self.es_m.load_combined_query(query)
        response = self.es_m.scroll(size=bs, field_scroll=self.field)
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']

        while total_docs > 0:
            data = ''
            for document in response['hits']['hits']:
                new_field = []
                for fact in document['_source'][self.field]:
                    if fact['fact'] != self.key and fact['str_val'] != self.val:
                        new_field.append(fact)

                # Update dataset
                data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
                document = {'doc': {self.field: new_field}}
                data += json.dumps(document)+'\n'

            response = self.es_m.scroll(scroll_id=scroll_id, size=bs, field_scroll=self.field)
            total_docs = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            self.es_m.plain_post_bulk(self.es_m.es_url, data)