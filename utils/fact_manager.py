import sys
import re
import json
import logging
import requests
import itertools
import traceback
from typing import List
from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from texta.settings import FACT_PROPERTIES, ERROR_LOGGER
from task_manager.task_manager import create_task
from task_manager.tasks.task_types import TaskTypes
from task_manager.tasks.workers.management_workers.management_task_params import ManagerKeys
from task_manager.models import Task

class FactManager:
    """ Manage Searcher facts, like deleting/storing, adding facts.
    """

    def __init__(self,request):
        self.request = request
        self.es_params = request.POST
        self.ds = Datasets().activate_datasets(request.session)
        self.es_m = self.ds.build_manager(ES_Manager)
        # Maybe should come from some settings file
        self.max_name_len = 25

    def start_fact_deleter_task(self, rm_facts_dict, doc_id=None):
        """Remove facts from documents, by starting fact_deleter management task.
        
        Arguments:
            rm_facts_dict {Dict[str: List[str]]} -- Dict of fact values to remove
            Examples:
                General format - { 'factname1': ['factvalue1','factvalue2', ...]}
                Real example - {'CITY': ['tallinna', 'tallinn'], 'CAR': ['bmw', 'audi']}
        
        Keyword Arguments:
            doc_id {str} -- If present, deletes the facts only in a given document (default: {None})
        """
        task_type = TaskTypes.MANAGEMENT_TASK
        description = 'fact_manager_fact_deletion'
        params = {
            'fact_deleter_fact_values': rm_facts_dict,
            'fact_deleter_doc_id': doc_id,
            'task_type': task_type,
            'manager_key': ManagerKeys.FACT_DELETER,
            'description': description,
            'dataset': self.request.session['dataset']
        }

        task_id = create_task(task_type, description, params, self.request.user)
        task = Task.objects.get(pk=task_id)
        task.update_status(Task.STATUS_QUEUED)


class FactGraph(FactManager):
    def __init__(self, request, es_params, search_size):
        super().__init__(request)
        self.es_params = es_params
        self.search_size = search_size
        # D3 shapes
        self.shapes = ["circle", "cross", "diamond", "square", "triangle-down", "triangle-up"]


    def fact_graph(self):
        facts, fact_combinations, unique_fact_names = self.facts_via_aggregation(size=self.search_size)
        # Get cooccurrences and remove values with 0
        fact_combinations = {k:v for k,v in dict(zip(fact_combinations, self.count_cooccurrences(fact_combinations))).items() if v != 0}
        types = dict(zip(unique_fact_names, itertools.cycle(self.shapes)))

        nodes = []
        max_node_size = 0
        min_node_size = 0
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


class FactAdder(FactManager):
    def __init__(self, request):
        self.request = request

    def start_fact_adder_task(self, fact_name: str, fact_value: str, fact_field: str, doc_id: str, method: str, match_type: str, case_sens: bool):
        """Adds custom facts to documents, by starting fact_adder management task."""
        task_type = TaskTypes.MANAGEMENT_TASK
        description = 'fact_manager_fact_adding'
        params = {
            'fact_name': fact_name,
            'fact_value': fact_value,
            'fact_field': fact_field,
            'doc_id': doc_id,
            'method': method,
            'match_type': match_type,
            'case_sens': case_sens,
            'task_type': task_type,
            'manager_key': ManagerKeys.FACT_ADDER,
            'description': description,
            'dataset': self.request.session['dataset']
        }

        task_id = create_task(task_type, description, params, self.request.user)
        task = Task.objects.get(pk=task_id)
        task.update_status(Task.STATUS_QUEUED)
