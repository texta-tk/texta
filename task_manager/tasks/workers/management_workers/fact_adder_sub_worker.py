import logging
import json
import re
from task_manager.tasks.workers.base_worker import BaseWorker
from task_manager.tools import ShowProgress
from texta.settings import ERROR_LOGGER, FACT_PROPERTIES, FACT_FIELD

class FactAdderSubWorker(BaseWorker):

    def __init__(self, es_m, task_id, params, scroll_size=10000, time_out='10m'):
        self.es_m = es_m
        self.task_id = task_id
        self.params = params
        self.scroll_size = scroll_size
        self.scroll_time_out = time_out

        self.fact_name = None
        self.fact_value = None
        self.fact_field = None
        self.doc_id = None
        self.method = None
        self.match_type = None
        self.case_sens = None
        self.nested_field = None

    def run(self):
        try:
            self.parse_params()
            result = self.add_facts()
            return json.dumps(result)
        except:
            logging.getLogger(ERROR_LOGGER).error('A problem occurred when attempted to run fact_deleter_worker.', exc_info=True, extra={
                'params': self.params,
                'task_id': self.task_id
            })
            # Return empty result
            return {}


    def parse_params(self):
        self.fact_name = self.params['fact_name']
        self.fact_value = self.params['fact_value']
        self.fact_field = self.params['fact_field']
        self.doc_id = self.params['doc_id']
        self.method = self.params['method']
        self.match_type = self.params['match_type']
        self.case_sens = self.params['case_sens']
        self.nested_field = None

        if len(self.fact_field.split('.')) > 1:
            self.nested_field = self.fact_field.split('.')


    def add_facts(self):
        if self.method == 'select_only':
            result = self.fact_to_doc()
        elif self.method == 'all_in_doc':
            result = self.doc_matches_to_facts()
        elif self.method == 'all_in_dataset':
            result = self.matches_to_facts()
        return result


    def fact_to_doc(self):
        """Add a fact to a certain document with given fact, span, and the document _id"""
        query = {"query": {"terms": {"_id": [self.doc_id] }}}
        response = self.es_m.perform_query(query)
        hits = response['hits']['hits']
        # If texta_facts not in document
        if FACT_FIELD not in hits[0]['_source']:
            self.es_m.update_mapping_structure(FACT_FIELD, FACT_PROPERTIES)

        data = ''
        for document in hits:
            content = self._derive_content(document)
            match = re.search(r"{}".format(self.fact_value), content, re.IGNORECASE | re.MULTILINE)
            save_val = match.group().lower() if not self.case_sens else match.group()
            new_fact = {'fact': self.fact_name, 'str_val':  save_val, 'doc_path': self.fact_field, 'spans': str([list(match.span())])}
            if FACT_FIELD not in document['_source']:
                document['_source'][FACT_FIELD] = [new_fact]
            else:
                document['_source'][FACT_FIELD].append(new_fact)

            data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
            document = {'doc': {FACT_FIELD: document['_source'][FACT_FIELD]}}
            data += json.dumps(document)+'\n'
        response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
        return {'fact_count': 1, 'status': 'success'}


    def doc_matches_to_facts(self):
        """Add all matches in a certain doc as a fact"""
        query = {"query": {"terms": {"_id": [self.doc_id] }}}
        response = self.es_m.perform_query(query)
        hits = response['hits']['hits']
        # If texta_facts not in document
        if FACT_FIELD not in hits[0]['_source']:
            self.es_m.update_mapping_structure(FACT_FIELD, FACT_PROPERTIES)

        fact_count = 0
        data, fact_count = self._derive_match_spans(hits, fact_count)
        response = self.es_m.plain_post_bulk(self.es_m.es_url, data)
        return {'fact_count': fact_count, 'status': 'success'}


    def matches_to_facts(self):
        """Add all matches in dataset as a fact"""

        if self.match_type == 'string':
            # Match the word everywhere in text
            query = {"main": {'query': {'query_string': {'query': '*{}*'.format(self.fact_value), 'fields': [self.fact_field]}}}}
        else:
            # Match prefix, or separate word
            query =  {"main": {"query": {"multi_match" : {"query":self.fact_value, "fields": [self.fact_field], "type": self.match_type}}}}

        # response = self.es_m.perform_query(query)
        self.es_m.load_combined_query(query)
        response = self.es_m.scroll(size=self.scroll_size,time_out='3m', field_scroll=self.fact_field)
        scroll_id = response['_scroll_id']
        total_docs = response['hits']['total']
        # For partial update
        doc_ids = [x['_id'] for x in response['hits']['hits'] if '_id' in x]

        show_progress = ShowProgress(self.task_id, multiplier=total_docs/self.scroll_size)
        show_progress.set_total(total_docs)
        show_progress.update_view(0)

        # If texta_facts not in document
        hits = response['hits']['hits']
        docs_left = total_docs
        fact_count = 0
        if hits:
            try:
                self.es_m.update_mapping_structure(FACT_FIELD, FACT_PROPERTIES)
                while len(response['hits']['hits']):
                    data, fact_count = self._derive_match_spans(response['hits']['hits'], fact_count)
                    self.es_m.plain_post_bulk(self.es_m.es_url, data)
                    self.es_m.update_documents_by_id(doc_ids)
                    response = self.es_m.scroll(scroll_id=scroll_id,time_out='3m', size=self.scroll_size, field_scroll=FACT_FIELD)
                    if response['hits']:
                        docs_left -= len(response['hits']['hits'])
                        scroll_id = response['_scroll_id']
                        # For partial update
                        doc_ids = [x['_id'] for x in response['hits']['hits'] if '_id' in x]
                    show_progress.update(docs_left)
                # Update the last patch
                update_response = self.es_m.update_documents_by_id(doc_ids)
                
            except Exception as e:
                logging.getLogger(ERROR_LOGGER).exception(e)
                return {'fact_count': fact_count, 'status': 'scrolling_error'}
        else:
            return {'fact_count': 0, 'status': 'no_hits'}
        self.es_m.clear_scroll(scroll_id)
        return {'fact_count': fact_count, 'status': 'success'}


    def _derive_match_spans(self, hits, fact_count):
        if self.match_type == 'phrase':
            pattern = r"\b{}\b"
        elif self.match_type == 'phrase_prefix':
            pattern = r"\b{}\w*"
        elif self.match_type == 'string':
            pattern = r"\w*{}\w*"

        data = ''
        for document in hits:
            content = self._derive_content(document)
            new_facts = []
            for match in re.finditer(pattern.format(self.fact_value), content, re.IGNORECASE):
                save_val = match.group().lower() if not self.case_sens else match.group()
                new_facts.append({'fact': self.fact_name, 'str_val':  save_val, 'doc_path': self.fact_field, 'spans': str([list(match.span())])})
                fact_count += 1
            data = self._append_fact_to_doc(document, data, new_facts)
        return data, fact_count


    def _append_fact_to_doc(self, document, data, new_facts):
        if FACT_FIELD not in document['_source']:
            document['_source'][FACT_FIELD] = new_facts
        else:
            document['_source'][FACT_FIELD].extend(new_facts)

        data += json.dumps({"update": {"_id": document['_id'], "_type": document['_type'], "_index": document['_index']}})+'\n'
        document = {'doc': {FACT_FIELD: document['_source'][FACT_FIELD]}}
        data += json.dumps(document)+'\n'
        return data

    def _derive_content(self, document):
        if self.nested_field:
            content = document['_source']
            for key in self.nested_field:
                content = content[key]
        else:
            content = document['_source'][self.fact_field]
        return content
