from elasticsearch import Elasticsearch
import urllib
import json

from toolkit.elastic.core import ElasticCore
from toolkit.settings import ES_URL

ES_SCROLL_SIZE = 500

class ElasticSearcher:
    """
    Everything related to performing searches in Elasticsearch
    """
    OUT_RAW         = 'raw'
    OUT_DOC         = 'doc'
    OUT_DOC_WITH_ID = 'doc_with_id'
    OUT_TEXT        = 'text'
    EMPTY_QUERY     = {"query": {"match_all": {}}}

    def __init__(self, field_data=[],
                       query=EMPTY_QUERY,
                       scroll_size=ES_SCROLL_SIZE,
                       output=OUT_DOC,
                       callback_progress=None,
                       scroll_limit=None,
                       ignore_ids=(), 
                       text_processor=None):
        """
        Output options: document (default), text (lowered & stopwords removed), sentences (text + line splitting), raw (raw elastic output)
        """
        self.field_data = self._parse_field_data(field_data)
        self.indices = ','.join([field['index'] for field in field_data])
        self.query = query
        self.scroll_size = scroll_size
        self.scroll_limit = scroll_limit
        self.ignore_ids = ignore_ids
        self.output = output
        self.callback_progress = callback_progress
        self.core = ElasticCore()
        self.text_processor = text_processor

        if self.callback_progress:
            total_elements = self.count()
            callback_progress.set_total(total_elements)


    def __iter__(self):
        """
        Iterator for iterating through scroll
        """
        return self.scroll()


    @staticmethod
    def _parse_field_data(field_data):
        """
        Parses field data list into dict with index names as keys and field paths as list of strings
        """
        parsed_data = {}
        for field in field_data:
            if field['index'] not in parsed_data:
                parsed_data[field['index']] = []
            parsed_data[field['index']].append(field['field_path'])
        return parsed_data


    @staticmethod
    def doc_to_texts(doc, sentences=False):
        texts = []
        for text in doc.values():
            text = text.strip().lower()
            # remove stopwords

            if sentences == True:
                lines = text.split('\n')
                for line in lines:
                    if line:
                        texts.append(line.strip())
            else:
                texts.append(text)
        return texts


    def _parse_doc(self, doc):
        """
        Parses Elasticsearch hit into something nicer
        """
        parsed_doc = {}
        for index, field_paths in self.field_data.items():
            if doc['_index'] == index:
                for field_path in field_paths:
                    decoded_text = doc['_source']
                    for k in field_path.split('.'):
                        # get nested fields encoded as: 'field.sub_field'
                        try:
                            decoded_text = decoded_text[k]
                        except:
                            decoded_text = ""
                    if decoded_text:
                        parsed_doc[field_path] = decoded_text
        return parsed_doc


    def count(self):
        response = self.core.es.search(index=self.indices, body=self.query)
        return response['hits']['total']


    def search(self):
        response = self.core.es.search(index=self.indices, body=self.query)
        if self.output == self.OUT_DOC:
            return [self._parse_doc(doc) for doc in response['hits']['hits']]
        else:
            return response


    def scroll(self):
        page = self.core.es.search(index=self.indices, body=self.query, scroll='1m', size=self.scroll_size)
        scroll_id = page['_scroll_id']
        current_page = 1

        page_size = len(page['hits']['hits'])
        num_scrolled = page_size

        while page_size > 0:
            # limit scroll output if needed
            if self.scroll_limit and num_scrolled >= self.scroll_limit:
                break
            # process output
            if self.output in (self.OUT_DOC, self.OUT_DOC_WITH_ID, self.OUT_TEXT):
                if self.callback_progress:
                    self.callback_progress.update(page_size)
                for hit in page['hits']['hits']:
                    if hit['_id'] not in self.ignore_ids:
                        num_scrolled += 1
                        parsed_doc = self._parse_doc(hit)
                        if self.output == self.OUT_TEXT:
                            for field in parsed_doc.values():
                                processed_field = self.text_processor.process(field)
                                for text in processed_field:
                                    yield text
                        elif self.output in (self.OUT_DOC, self.OUT_DOC_WITH_ID):
                            if self.text_processor:
                                parsed_doc = {k: self.text_processor.process(v) for k, v in parsed_doc.items()}
                            if self.OUT_DOC_WITH_ID:
                                parsed_doc['_id'] = hit['_id']
                            yield parsed_doc

            # return raw hit
            elif self.output == self.OUT_RAW:
                page = [doc for doc in page if doc['_id'] not in self.ignore_ids]
                num_scrolled += len(page)
                yield page

            # get new page
            page = self.core.es.scroll(scroll_id=scroll_id, scroll='1m')
            scroll_id = page['_scroll_id']
            page_size = len(page['hits']['hits'])
            current_page += 1
