import logging
import json
from ..base_worker import BaseWorker
from task_manager.tools import ShowProgress
from utils.fact_manager import FactManager
from texta.settings import ERROR_LOGGER

class FactDeleterSubWorker(BaseWorker):

    def __init__(self, es_m, task_id, params, scroll_size=10000, time_out='10m'):
        self.es_m = es_m
        self.task_id = task_id
        self.params = params
        self.scroll_size = scroll_size
        self.scroll_time_out = time_out
        self.f_field = FactManager.f_field

    def run(self):
        # steps = ["preparing", "deleting documents", "done"]
        # show_progress = ShowSteps(self.task_id, steps)
        # show_progress.update_view()
        
        try:
            rm_facts_dict, doc_id = self.parse_params()
            query = self._fact_deletion_query(rm_facts_dict, doc_id)
            self.es_m.load_combined_query(query)

            import pdb;pdb.set_trace()
            self.remove_facts_from_document(rm_facts_dict, doc_id)
        except:
            logging.getLogger(ERROR_LOGGER).error('A problem occurred when attempted to run fact_deleter_worker.', exc_info=True, extra={
                'params': self.params,
                'task_id': self.task_id
            })


    def remove_facts_from_document(self, rm_facts_dict, doc_id=None):
        """Remove facts from documents.
        
        Arguments:
            rm_facts_dict {Dict[str: List[str]]} -- Dict of fact values to remove
            Examples:
                General format - { 'factname1': ['factvalue1','factvalue2', ...]}
                Real example - {'CITY': ['tallinna', 'tallinn'], 'CAR': ['bmw', 'audi']}
        
        Keyword Arguments:
            doc_id {str} -- If present, deletes the facts only in a given document (default: {None})
        """

        try:
            response = self.es_m.scroll(size=self.scroll_size, field_scroll=self.f_field)
            import pdb;pdb.set_trace()
            
            scroll_id = response['_scroll_id']
            total_docs = response['hits']['total']
            show_progress = ShowProgress(self.task_id, multiplier=total_docs/self.scroll_size)
            show_progress.set_total(total_docs)
            show_progress.update_view(0)


            docs_left = total_docs # DEBUG
            print('Starting.. Total docs - ', total_docs) # DEBUG
            while total_docs > 0:
                try:
                    print('Docs left:', docs_left) # DEBUG
                    data = ''
                    for document in response['hits']['hits']:
                        new_field = [] # The new facts field
                        for fact in document['_source'][self.f_field]:
                            # If the fact name is in rm_facts_dict keys
                            if fact["fact"] in rm_facts_dict:
                                # If the fact value is not in the delete key values
                                if fact['str_val'] not in rm_facts_dict[fact["fact"]]:
                                    new_field.append(fact)
                            else:
                                new_field.append(fact)
                        # Update dataset
                        data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
                        document = {'doc': {self.f_field: new_field}}
                        data += json.dumps(document)+'\n'
                    response = self.es_m.scroll(scroll_id=scroll_id, size=self.scroll_size, field_scroll=self.f_field)
                    total_docs = len(response['hits']['hits'])
                    docs_left -= self.scroll_size # DEBUG
                    scroll_id = response['_scroll_id']
                    show_progress.update(total_docs)
                    self.es_m.plain_post_bulk(self.es_m.es_url, data)
                except:
                    logging.getLogger(ERROR_LOGGER).error('A problem occurred during scrolling of fact deletion.', exc_info=True, extra={
                        'total_docs': total_docs,
                        'response': response,
                        'rm_facts_dict': rm_facts_dict
                    })
            print('DONE') # DEBUG
            show_progress.update_view(100.0)
        except:
            logging.getLogger(ERROR_LOGGER).error('A problem occurred when attempting to delete facts.', exc_info=True, extra={
                'rm_facts_dict': rm_facts_dict,
                'response': response,
            })


    def _fact_deletion_query(self, rm_facts_dict, doc_id):
        '''Creates the query for fact deletion based on dict of facts {nampe: val}'''
        fact_queries = []
        for key in rm_facts_dict:
            for val in rm_facts_dict[key]:
                terms = [{"term": {self.f_field+".fact": key}},{"term": {self.f_field+".str_val": val}}]
                if doc_id:
                    terms.append({"term": {"_id": doc_id}})
                fact_queries.append({"bool": {"must": terms}})

        query = {"main": {"query": {"nested": {"path": self.f_field,"query":
         {"bool":{"should":fact_queries}}}},"_source": [self.f_field]}}
        return query

    def parse_params(self):
        if 'fact_deleter_fact_values' in self.params:
            rm_facts_dict = self.params['fact_deleter_fact_values']
        else:
            raise UserWarning('Fact values not present in params')

        doc_id = self.params['fact_deleter_doc_id'] if 'fact_deleter_doc_id' in self.params else None

        return rm_facts_dict, doc_id