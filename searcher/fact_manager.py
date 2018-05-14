from utils.datasets import Datasets
from utils.es_manager import ES_Manager
import json
import requests

class FactManager:
    """ Manage Searcher facts, like deleting/storing, adding facts.
    """
    def __init__(self,request):
        self.key = list(request.POST.keys())[0]
        self.val = request.POST[self.key]

        ds = Datasets().activate_dataset(request.session)
        self.index = ds.get_index()
        self.mapping = ds.get_mapping()
        self.es_m = ES_Manager(self.index, self.mapping)
        self.field = 'texta_facts'

    def remove_facts_from_document(self):
        query = {"main": {"query": {"nested":
            {"path": self.field,"query": {"bool": {"must":
            [{ "match": {self.field + ".fact": self.key }},
            { "match": {self.field + ".str_val":  self.val }}]}}}},
            "_source": [self.field]}}

        self.es_m.load_combined_query(query)
        response = self.es_m.scroll()

        data = ''
        for document in response['hits']['hits']:
            removed_facts = []
            new_field = []
            for fact in document['_source'][self.field]:
                if fact['fact'] == self.key and fact['str_val'] == self.val:
                    removed_facts.append(fact)
                else:
                    new_field.append(fact)

            # Update dataset
            data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
            document = {'doc': {self.field: new_field}}
            data += json.dumps(document)+'\n'
        self.es_m.plain_post_bulk(self.es_m.es_url, data)

    def tag_documents_with_facts(self, es_params, tag_name, tag_value, tag_field):
        self.es_m.build(es_params)
        self.es_m.load_combined_query(self.es_m.combined_query)

        response = self.es_m.scroll()

        data = ''
        for document in response['hits']['hits']:
            if 'mlp' in tag_field:
                split_field = tag_field.split('.')
                span = [0, len(document['_source'][split_field[0]][split_field[1]])]
            else:
                span = [0, len(document['_source'][tag_field].strip())]
            document['_source'][self.field].append({"str_val": tag_value, "spans": str([span]), "fact": tag_name, "doc_path":tag_field})

            data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
            document = {'doc': {self.field: document['_source'][self.field]}}
            data += json.dumps(document)+'\n'
        self.es_m.plain_post_bulk(self.es_m.es_url, data)
        response = requests.post('{0}/{1}/_update_by_query?refresh&conflicts=proceed'.format(self.es_m.es_url, self.index), headers=self.es_m.HEADERS)
