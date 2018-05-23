from utils.datasets import Datasets
from utils.es_manager import ES_Manager
import json
import requests
import itertools

class FactManager:
    """ Manage Searcher facts, like deleting/storing, adding facts.
    """
    def __init__(self,request):
        self.es_params = request.POST
        self.key = list(request.POST.keys())[0]
        self.val = request.POST[self.key]

        self.ds = Datasets().activate_dataset(request.session)
        self.index = self.ds.get_index()
        self.mapping = self.ds.get_mapping()
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

    def count_cooccurrences(self, fact_pairs):
        """Finds the counts of cooccuring facts
        
        Arguments:
            fact_pairs {list of tuples of tuples} -- Example:[(('ORG', 'Riigikohus'),('PER', 'Jaan')), (('ORG', 'Riigikohus'),('PER', 'Peeter'))]
        
        Returns:
            [int list] -- Occurances of the given facts
        """
        queries = []
        for fact_pair in fact_pairs:
            fact_constraints = []

            for fact in fact_pair:
                constraint = {"nested": {"path": "texta_facts", "query": {"bool":{"must": [{"term": {"texta_facts.fact": fact[0]}}, {"term": {"texta_facts.str_val": fact[1]}}]}}}}
                fact_constraints.append(constraint)

            query = {"query": {"bool": {"must": fact_constraints}}, "size": 0}
            queries.append(json.dumps(query))

        header = json.dumps({"index": self.index})
        data = "\n".join(["{0}\n{1}".format(header, q) for q in queries])+"\n"

        responses = requests.post("{0}/{1}/_msearch".format(self.es_m.es_url, self.index), data=data, headers={"Content-Type":"application/json"})
        counts = [response["hits"]["total"] for response in responses.json()['responses']]

        return counts

    def facts_via_aggregation(self):
        from pprint import pprint

        aggs = {"facts": {"nested": {"path": "texta_facts"}, "aggs": {"fact_names": {"terms": {"field": "texta_facts.fact"}, "aggs": {"fact_values": {"terms": {"field": "texta_facts.str_val", "size": 3}}}}}}}

        self.es_m.build(self.es_params)
        self.es_m.set_query_parameter('aggs', aggs)
        response = self.es_m.search()
        # response = requests.post("{0}/{1}/{2}/_search".format(self.es_m.es_url, self.index, self.mapping), data=json.dumps(query), headers={"Content-Type":"application/json"})
        response_aggs = response['aggregations']['facts']['fact_names']['buckets']
        pprint(response_aggs)
        facts = []
        fact_combinations = []
        for bucket in response_aggs:
            for fact in bucket['fact_values']['buckets']:
                facts.append({bucket['key']: fact['key'], 'doc_count': fact['doc_count']})
                fact_combinations.append((bucket['key'], fact['key']))

        print(len(fact_combinations))
        fact_combinations = [x for x in itertools.combinations(fact_combinations, 2)]
        print(len(fact_combinations))
        fact_combinations = dict(zip(fact_combinations, self.count_cooccurrences(fact_combinations)))
        import pdb;pdb.set_trace()


