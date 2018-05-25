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
        self.ds = Datasets().activate_dataset(request.session)
        self.index = self.ds.get_index()
        self.mapping = self.ds.get_mapping()
        self.es_m = ES_Manager(self.index, self.mapping)
        self.field = 'texta_facts'

    def remove_facts_from_document(self, key, val):
        '''remove a certain fact from all documents given a [str]key and [str]val'''

        query = {"main": {"query": {"nested":
            {"path": self.field,"query": {"bool": {"must":
            [{ "match": {self.field + ".fact": key }},
            { "match": {self.field + ".str_val":  val }}]}}}},
            "_source": [self.field]}}

        self.es_m.load_combined_query(query)
        response = self.es_m.scroll()

        data = ''
        for document in response['hits']['hits']:
            removed_facts = []
            new_field = []
            for fact in document['_source'][self.field]:
                if fact['fact'] == key and fact['str_val'] == val:
                    removed_facts.append(fact)
                else:
                    new_field.append(fact)

            # Update dataset
            data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
            document = {'doc': {self.field: new_field}}
            data += json.dumps(document)+'\n'
        self.es_m.plain_post_bulk(self.es_m.es_url, data)

    def tag_documents_with_fact(self, es_params, tag_name, tag_value, tag_field):
        '''Used to tag all documents in the current search with a certain fact'''

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
        """Finds all facts from current search.

        Returns:
            facts - [dict] -- Details for each fact, ex: {'PER - kostja': {'id': 0, 'name': 'PER', 'value': 'kostja', 'doc_count': 44}}
            fact_combinations - [list of tuples] -- All possible combinations of all facts: [(('FIRST_FACTNAME', 'FIRST_FACTVAL'), ('SECOND_FACTNAME', 'SECOND_FACTVAL'))]
            unique_fact_names - [list of string] -- All unique fact names
        """

        aggs = {"facts": {"nested": {"path": "texta_facts"}, "aggs": {"fact_names": {"terms": {"field": "texta_facts.fact"}, "aggs": {"fact_values": {"terms": {"field": "texta_facts.str_val", "size": 3}}}}}}}
        self.es_m.build(self.es_params)
        self.es_m.set_query_parameter('aggs', aggs)
        response = self.es_m.search()
        response_aggs = response['aggregations']['facts']['fact_names']['buckets']

        facts = {}
        fact_combinations = []
        fact_count = 0
        unique_fact_names = []
        for bucket in response_aggs:
            unique_fact_names.append(bucket['key'])
            for fact in bucket['fact_values']['buckets']:
                facts[bucket['key'] + " - " + fact['key']] = {'id': fact_count, 'name': bucket['key'], 'value': fact['key'], 'doc_count': fact['doc_count']}
                fact_combinations.append((bucket['key'], fact['key']))
                fact_count += 1

        fact_combinations = [x for x in itertools.combinations(fact_combinations, 2)]
        return (facts, fact_combinations, unique_fact_names)


    def fact_graph(self):
        facts, fact_combinations, unique_fact_names = self.facts_via_aggregation()

        # Get cooccurrences and remove values with 0
        fact_combinations = {k:v for k,v in dict(zip(fact_combinations, self.count_cooccurrences(fact_combinations))).items() if v != 0}
        shapes = ["circle", "cross", "diamond", "square", "triangle-down", "triangle-up"]
        types = dict(zip(unique_fact_names,shapes))

        nodes = []
        max_node_size = 0
        min_node_size = 0
        for fact in facts:
            max_node_size = max(max_node_size, facts[fact]['doc_count'])
            min_node_size = min(max_node_size, facts[fact]['doc_count'])
            nodes.append({"source": facts[fact]['id'], "size": facts[fact]['doc_count'], "score": facts[fact]['doc_count'], "name": facts[fact]['name'], "id": facts[fact]['value'], "type": types[facts[fact]['name']]})

        links = []
        max_link_size = 0
        for fact in fact_combinations.keys():
            max_link_size = max(max_link_size, fact_combinations[fact])
            links.append({"source": facts[fact[0][0] + " - " + fact[0][1]]['id'], "target": facts[fact[1][0] + " - " + fact[1][1]]['id'], "count": fact_combinations[fact]})

        graph_data = json.dumps({"nodes": nodes, "links": links})
        return (graph_data, unique_fact_names, max_node_size, max_link_size, min_node_size)
