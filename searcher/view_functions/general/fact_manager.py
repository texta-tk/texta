from utils.datasets import Datasets
from utils.es_manager import ES_Manager
import sys
import re
import json
import requests
import itertools
import traceback
from utils.log_manager import LogManager
from texta.settings import FACT_PROPERTIES

class FactManager:
    """ Manage Searcher facts, like deleting/storing, adding facts.
    """
    def __init__(self,request):
        self.es_params = request.POST
        self.ds = Datasets().activate_datasets(request.session)
        self.es_m = self.ds.build_manager(ES_Manager)
        self.field = 'texta_facts'
        # Maybe should come from some settings file
        self.max_name_len = 15
        self.bs = 7500

    def remove_facts_from_document(self, rm_facts_dict):
        '''remove a certain fact from all documents given a [str]key and [str]val'''
        logger = LogManager(__name__, 'FactManager remove_facts_from_document')

        try:
            query = self._fact_deletion_query(rm_facts_dict)
            self.es_m.load_combined_query(query)
            response = self.es_m.scroll(size=self.bs, field_scroll=self.field)
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
                            if fact['str_val'] not in rm_facts_dict.getlist(fact["fact"]):
                                new_field.append(fact)
                        else:
                            new_field.append(fact)
                    # Update dataset
                    data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
                    document = {'doc': {self.field: new_field}}
                    data += json.dumps(document)+'\n'
                response = self.es_m.scroll(scroll_id=scroll_id, size=self.bs, field_scroll=self.field)
                total_docs = len(response['hits']['hits'])
                docs_left -= self.bs # DEBUG
                scroll_id = response['_scroll_id']
                self.es_m.plain_post_bulk(self.es_m.es_url, data)
            print('DONE') # DEBUG

            logger.set_context('docs_left', total_docs)
            logger.set_context('batch', batch)
            logger.info('remove_facts_from_document')
        except:
            print(traceback.format_exc())
            logger.set_context('es_params', self.es_params)
            logger.exception('remove_facts_from_document_failed, {}'.format(traceback.format_exc()))


    def _fact_deletion_query(self, rm_facts_dict):
        '''Creates the query for fact deletion based on dict of facts {nampe: val}'''
        fact_queries = []
        for key in rm_facts_dict:
            for val in rm_facts_dict.getlist(key):
                fact_queries.append(
                    {"bool": {"must": [{"match": {self.field+".fact": key}},
                    {"match": {self.field+".str_val": val}}]}})

        query = {"main": {"query": {"nested":
            {"path": self.field,"query": {"bool": {"should":fact_queries
            }}}},"_source": [self.field]}}

        return query


    def count_cooccurrences(self, fact_pairs):
        """Finds the counts of cooccuring facts

        Arguments:
            fact_pairs {list of tuples of tuples} -- Example:[(('ORG', 'Riigikohus'),('PER', 'Jaan')), (('ORG', 'Riigikohus'),('PER', 'Peeter'))]

        Returns:
            [int list] -- Occurances of the given facts
        """
        dataset_str = self.es_m.stringify_datasets()
        
        queries = []
        for fact_pair in fact_pairs:
            fact_constraints = []

            for fact in fact_pair:
                constraint = {"nested": {"path": "texta_facts", "query": {"bool":{"must": [{"term": {"texta_facts.fact": fact[0]}}, {"term": {"texta_facts.str_val": fact[1]}}]}}}}
                fact_constraints.append(constraint)

            query = {"query": {"bool": {"must": fact_constraints}}, "size": 0}
            header = {"index": dataset_str}
            
            queries.append(json.dumps(header))
            queries.append(json.dumps(query))
        
        responses = self.es_m.perform_queries(queries)
        counts = [response["hits"]["total"] for response in responses]

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
        max_node_size = 0
        max_link_size = 0
        for i, fact in enumerate(facts):
            nodes.append({"source": facts[fact]['id'], "size": facts[fact]['doc_count'], "score": facts[fact]['doc_count'], "name": facts[fact]['name'], "id": facts[fact]['value'], "type": types[facts[fact]['name']]})
            # Track max/min count
            count = facts[fact]['doc_count']
            if i == 0:
                max_node_size = count
                min_node_size = count
            max_node_size = max(max_node_size, count)
            min_node_size = min(min_node_size, count)

        links = []
        max_link_size = 0
        for fact in fact_combinations.keys():
            max_link_size = max(max_link_size, fact_combinations[fact])
            links.append({"source": facts[fact[0][0] + " - " + fact[0][1]]['id'], "target": facts[fact[1][0] + " - " + fact[1][1]]['id'], "count": fact_combinations[fact]})

        graph_data = json.dumps({"nodes": nodes, "links": links})
        return (graph_data, unique_fact_names, max_node_size, max_link_size, min_node_size)


    def tag_documents_with_fact(self, es_params, tag_name, tag_value, tag_field):
        '''Used to tag all documents in the current search with a certain fact'''
        # Crop fact name if its too long
        tag_name = tag_name[:self.max_name_len]
        self.es_m.build(es_params)
        self.es_m.load_combined_query(self.es_m.combined_query)
        response = self.es_m.scroll()

        data = ''
        for document in response['hits']['hits']:
            if 'mlp' in tag_field:
                split_field = tag_field.split('.')
                tag_span = [0, len(document['_source'][split_field[0]][split_field[1]])]
            else:
                tag_span = [0, len(document['_source'][tag_field].strip())]
            document['_source'][self.field].append({"str_val": tag_value, "spans": str([tag_span]), "fact": tag_name, "doc_path":tag_field})

            data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
            document = {'doc': {self.field: document['_source'][self.field]}}
            data += json.dumps(document)+'\n'

        response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
        response = self.es_m.update_documents()
        return response


    # def fact_to_doc(self, es_params, fact_name, fact_value, fact_field, fact_span, doc_id):
    #     """Add a fact to a certain document with given fact, span, and the document _id"""
    #     # Crop fact name if its too long
    #     fact_name = fact_name[:self.max_name_len]
    #     query = {"query": {"terms": {"_id": [doc_id] }}}
    #     response = self.es_m.perform_query(query)
    #     hits = response['hits']['hits']
    #     # If texta_facts not in document
    #     if self.field not in hits[0]['_source']:
    #         self.es_m.update_mapping_structure(self.field, FACT_PROPERTIES)

    #     data = ''
    #     for document in hits:
    #         if self.field not in document['_source']:
    #             document['_source'][self.field] = [{'fact': fact_name, 'str_val': fact_value, 'doc_path': fact_field, 'spans': str([fact_span])}]
    #         else:
    #             document['_source'][self.field].append({"fact": fact_name, "str_val": fact_value, "doc_path": fact_field, "spans": str([fact_span])})

    #         data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
    #         document = {'doc': {self.field: document['_source'][self.field]}}
    #         data += json.dumps(document)+'\n'
    #     response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
    #     response = self.es_m.update_documents()
    #     return response


    # def doc_matches_to_facts(self, es_params, fact_name, fact_value, fact_field, fact_span, doc_id):
    #     """Add all matches in a certain doc as a fact"""
    #     # Crop fact name if its too long
    #     fact_name = fact_name[:self.max_name_len]
    #     query = {"query": {"terms": {"_id": [doc_id] }}}
    #     response = self.es_m.perform_query(query)
    #     hits = response['hits']['hits']
    #     # If texta_facts not in document
    #     if self.field not in hits[0]['_source']:
    #         self.es_m.update_mapping_structure(self.field, FACT_PROPERTIES)

    #     data = ''
    #     for document in hits:
    #         if self.field not in document['_source']:
    #             document['_source'][self.field] = [{'fact': fact_name, 'str_val': fact_value, 'doc_path': fact_field, 'spans': str([fact_span])}]
    #         else:
    #             document['_source'][self.field].append({"fact": fact_name, "str_val": fact_value, "doc_path": fact_field, "spans": str([fact_span])})

    #         data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
    #         document = {'doc': {self.field: document['_source'][self.field]}}
    #         data += json.dumps(document)+'\n'
    #     response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
    #     response = self.es_m.update_documents()
    #     return response


    # def matches_to_facts(self, es_params, fact_name, fact_value, fact_field, fact_span, doc_id):
    #     """Add all matches in dataset as a fact"""        
    #     # Crop fact name if its too long
    #     fact_name = fact_name[:self.max_name_len]
    #     query = {"query": {"terms": {"_id": [doc_id] }}}
    #     response = self.es_m.perform_query(query)
    #     hits = response['hits']['hits']
    #     # If texta_facts not in document
    #     if self.field not in hits[0]['_source']:
    #         self.es_m.update_mapping_structure(self.field, FACT_PROPERTIES)

    #     data = ''
    #     for document in hits:
    #         if self.field not in document['_source']:
    #             document['_source'][self.field] = [{'fact': fact_name, 'str_val': fact_value, 'doc_path': fact_field, 'spans': str([fact_span])}]
    #         else:
    #             document['_source'][self.field].append({"fact": fact_name, "str_val": fact_value, "doc_path": fact_field, "spans": str([fact_span])})

    #         data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
    #         document = {'doc': {self.field: document['_source'][self.field]}}
    #         data += json.dumps(document)+'\n'
    #     response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
    #     response = self.es_m.update_documents()

    #     return response


class FactAdder(FactManager):
    def __init__(self, request, es_params, fact_name, fact_value, fact_field, doc_id, method, match_type, case_sens):
        super().__init__(request)
        self.es_params = es_params
        self.fact_name = fact_name[:self.max_name_len]
        self.fact_value = fact_value
        self.fact_field = fact_field
        self.doc_id = doc_id
        self.method = method
        self.match_type = match_type
        self.case_sens = case_sens


    def add_facts(self):
        logger = LogManager(__name__, 'FactAdder add_facts')
        try:
            if self.method == 'select_only':
                json_response = self.fact_to_doc()
            elif self.method == 'all_in_doc':
                json_response = self.doc_matches_to_facts()
            elif self.method == 'all_in_dataset':
                json_response = self.matches_to_facts()
            return json_response
        except Exception as e:
            print('-- Exception[{0}] {1}'.format(__name__, traceback.format_exc()))
            logger.error('adding_facts_failed, traceback: \n{}'.format(str(traceback.format_exc())))

    def fact_to_doc(self):
        """Add a fact to a certain document with given fact, span, and the document _id"""
        query = {"query": {"terms": {"_id": [self.doc_id] }}}
        response = self.es_m.perform_query(query)
        hits = response['hits']['hits']
        # If texta_facts not in document
        if self.field not in hits[0]['_source']:
            self.es_m.update_mapping_structure(self.field, FACT_PROPERTIES)

        data = ''
        for document in hits:
            match = re.search(r"{}".format(self.fact_value), document['_source'][self.fact_field], re.IGNORECASE | re.MULTILINE)
            save_val = match.group().lower() if not self.case_sens else match.group()
            new_fact = {'fact': self.fact_name, 'str_val':  save_val, 'doc_path': self.fact_field, 'spans': str([list(match.span())])}
            if self.field not in document['_source']:
                document['_source'][self.field] = [new_fact]
            else:
                document['_source'][self.field].append(new_fact)

            data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
            document = {'doc': {self.field: document['_source'][self.field]}}
            data += json.dumps(document)+'\n'
        response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
        # response = self.es_m.update_documents()
        return {'fact_count': 1, 'status': 'success'}


    def doc_matches_to_facts(self):
        """Add all matches in a certain doc as a fact"""
        query = {"query": {"terms": {"_id": [self.doc_id] }}}
        response = self.es_m.perform_query(query)
        hits = response['hits']['hits']
        # If texta_facts not in document
        if self.field not in hits[0]['_source']:
            self.es_m.update_mapping_structure(self.field, FACT_PROPERTIES)

        data, fact_count = self._derive_match_spans(hits)
        response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
        # response = self.es_m.update_documents()
        return {'fact_count': fact_count, 'status': 'success'}


    def matches_to_facts(self):
        """Add all matches in dataset as a fact"""
        logger = LogManager(__name__, 'FactAdder matches_to_facts ')

        if self.match_type == 'string':
            # Match the word everywhere in text
            query = {"main": {"query": {"regexp": {self.fact_field: {"match": r"\w*{}\w*".format(self.fact_value)}}}}}
        else:
            # Match prefix, or separate word
            query =  {"main": {"query": {"multi_match" : {"query":self.fact_value, "fields": [self.fact_field], "type": self.match_type}}}}

        # response = self.es_m.perform_query(query)
        self.es_m.load_combined_query(query)
        response = self.es_m.scroll(size=self.bs, field_scroll=self.fact_field)
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']
        # If texta_facts not in document
        hits = response['hits']['hits']

        if hits:
            try:
                fact_count = 0
                if self.field not in hits[0]['_source']:
                    self.es_m.update_mapping_structure(self.field, FACT_PROPERTIES)
                while total_docs > 0:
                    data, fact_count = self._derive_match_spans(hits)
                    response = self.es_m.scroll(scroll_id=scroll_id, size=self.bs, field_scroll=self.field)
                    total_docs = len(response['hits']['hits'])
                    scroll_id = response['_scroll_id']
                    self.es_m.plain_post_bulk(self.es_m.es_url, data)
            except Exception as e:
                print('-- Exception[{0}] {1}'.format(__name__, traceback.format_exc()))
                logger.error('scrolling error in FactAdder matches_to_facts, traceback: \n{}'.format(traceback.format_exc()))
                return {'fact_count': fact_count, 'status': 'scrolling_error'}
        else:
            return {'fact_count': 0, 'status': 'no_hits'}
        return {'fact_count': fact_count, 'status': 'success'}


    def _derive_match_spans(self, hits):
        if self.match_type == 'phrase':
            pattern = r"\b{}\b"
        elif self.match_type == 'phrase_prefix':
            pattern = r"\b{}\w*"
        elif self.match_type == 'string':
            pattern = r"\w*{}\w*"

        data = ''
        for document in hits:
            new_facts = []
            for i, match in enumerate(re.finditer(pattern.format(self.fact_value), document['_source'][self.fact_field], re.IGNORECASE)):
                save_val = match.group().lower() if not self.case_sens else match.group()
                new_facts.append({'fact': self.fact_name, 'str_val':  save_val, 'doc_path': self.fact_field, 'spans': str([list(match.span())])})
                fact_count = i
            data = self._append_fact_to_doc(document, data, new_facts)
        return data, fact_count


    def _append_fact_to_doc(self, document, data, new_facts):
        if self.field not in document['_source']:
            document['_source'][self.field] = new_facts
        else:
            document['_source'][self.field].extend(new_facts)

        data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
        document = {'doc': {self.field: document['_source'][self.field]}}
        data += json.dumps(document)+'\n'
        return data
