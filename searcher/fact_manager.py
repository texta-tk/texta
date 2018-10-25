from utils.datasets import Datasets
from utils.es_manager import ES_Manager
import json
import requests
import itertools
import traceback
from utils.log_manager import LogManager

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

    def remove_facts_from_document(self, rm_facts_dict, bs=7500):
        '''remove a certain fact from all documents given a [str]key and [str]val'''
        logger = LogManager(__name__, 'FACT MANAGER REMOVE FACTS')

        try:
            # Clears readonly block just in case the index has been set to read only
            self.es_m.clear_readonly_block()
            fact_queries = []
            for key in rm_facts_dict:
                for val in rm_facts_dict[key]:
                    fact_queries.append(
                        {"bool": {"must": [{"match": {self.field+".fact": key}},
                        {"match": {self.field+".str_val": val}}]}}
                        )

            query = {"main": {"query": {"nested":
                {"path": self.field,"query": {"bool": {"should":fact_queries
                }}}},"_source": [self.field]}}

            self.es_m.load_combined_query(query)
            response = self.es_m.scroll(size=bs, field_scroll=self.field)
            scroll_id = response['_scroll_id']
            total_docs = response['hits']['total']
            docs_left = total_docs # DEBUG
            print('Starting.. Total docs - ', total_docs) # DEBUG
            batch = 0
            while total_docs > 0:
                print('Docs left:', docs_left) # DEBUG
                data = ''
                for document in response['hits']['hits']:
                    new_field = [] # The new facts field
                    for fact in document['_source'][self.field]:
                        # If the fact name is in rm_facts_dict keys
                        if fact["fact"] in rm_facts_dict:
                            # If the fact value is not in the delete key values
                            if fact['str_val'] not in rm_facts_dict[key]:
                                new_field.append(fact)
                        else:
                            new_field.append(fact)
                    # Update dataset
                    data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
                    document = {'doc': {self.field: new_field}}
                    data += json.dumps(document)+'\n'
                response = self.es_m.scroll(scroll_id=scroll_id, size=bs, field_scroll=self.field)
                total_docs = len(response['hits']['hits'])
                docs_left -= bs # DEBUG
                scroll_id = response['_scroll_id']
                self.es_m.plain_post_bulk(self.es_m.es_url, data)
            print('DONE') # DEBUG

            logger.set_context('docs_left', total_docs)
            logger.set_context('batch', batch)
            logger.info('remove_facts_from_document')
        except:
            print(traceback.format_exc())
            logger.set_context('es_params', self.es_params)
            logger.exception('remove_facts_from_document_failed')

    def tag_documents_with_fact(self, es_params, tag_name, tag_value, tag_field, tag_span=None):
        '''Used to tag all documents in the current search with a certain fact'''

        self.es_m.build(es_params)
        self.es_m.load_combined_query(self.es_m.combined_query)

        response = self.es_m.scroll()

        data = ''
        for document in response['hits']['hits']:
            # If no custom span is passed in, make it the entire document
            if not tag_span:
                if 'mlp' in tag_field:
                    split_field = tag_field.split('.')
                    tag_span = [0, len(document['_source'][split_field[0]][split_field[1]])]
                else:
                    tag_span = [0, len(document['_source'][tag_field].strip())]
            document['_source'][self.field].append({"str_val": tag_value, "spans": str([tag_span]), "fact": tag_name, "doc_path":tag_field})

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

    def facts_via_aggregation(self, size=15):
        """Finds all facts from current search.
        Parameters:
            size - [int=15] -- Amount of fact values per fact name to search in query
        Returns:
            facts - [dict] -- Details for each fact, ex: {'PER - kostja': {'id': 0, 'name': 'PER', 'value': 'kostja', 'doc_count': 44}}
            fact_combinations - [list of tuples] -- All possible combinations of all facts: [(('FIRST_FACTNAME', 'FIRST_FACTVAL'), ('SECOND_FACTNAME', 'SECOND_FACTVAL'))]
            unique_fact_names - [list of string] -- All unique fact names
        """

        aggs = {"facts": {"nested": {"path": "texta_facts"}, "aggs": {"fact_names": {"terms": {"field": "texta_facts.fact"}, "aggs": {"fact_values": {"terms": {"field": "texta_facts.str_val", "size": size}}}}}}}
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


    def fact_graph(self, search_size):
        facts, fact_combinations, unique_fact_names = self.facts_via_aggregation(size=search_size)
        # Get cooccurrences and remove values with 0
        fact_combinations = {k:v for k,v in dict(zip(fact_combinations, self.count_cooccurrences(fact_combinations))).items() if v != 0}
        shapes = ["circle", "cross", "diamond", "square", "triangle-down", "triangle-up"]
        types = dict(zip(unique_fact_names, itertools.cycle(shapes)))

        nodes = []
        counts = []
        for fact in facts:
            counts.append(facts[fact]['doc_count'])
            nodes.append({"source": facts[fact]['id'], "size": facts[fact]['doc_count'], "score": facts[fact]['doc_count'], "name": facts[fact]['name'], "id": facts[fact]['value'], "type": types[facts[fact]['name']]})
        max_node_size = max(counts)
        min_node_size = min(counts)
        counts = None # Not needed anymore, release memory

        links = []
        max_link_size = 0
        for fact in fact_combinations.keys():
            max_link_size = max(max_link_size, fact_combinations[fact])
            links.append({"source": facts[fact[0][0] + " - " + fact[0][1]]['id'], "target": facts[fact[1][0] + " - " + fact[1][1]]['id'], "count": fact_combinations[fact]})

        graph_data = json.dumps({"nodes": nodes, "links": links})
        return (graph_data, unique_fact_names, max_node_size, max_link_size, min_node_size)
