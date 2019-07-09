import urllib
import json

from toolkit.elastic.core import ElasticCore
from toolkit.settings import ES_URL

ES_SCROLL_SIZE = 500
EMPTY_QUERY     = {"query": {"match_all": {}}}

class ElasticSearcher:
    """
    Everything related to performing searches in Elasticsearch
    """
    OUT_RAW         = 'raw'
    OUT_DOC         = 'doc'
    OUT_DOC_WITH_ID = 'doc_with_id'
    OUT_TEXT        = 'text'

    def __init__(self, field_data=[],
                       indices=[],
                       query=EMPTY_QUERY,
                       scroll_size=ES_SCROLL_SIZE,
                       output=OUT_DOC,
                       callback_progress=None,
                       scroll_limit=None,
                       ignore_ids=[], 
                       text_processor=None):
        """
        Output options: document (default), text (lowered & stopwords removed), sentences (text + line splitting), raw (raw elastic output)
        """
        self.core = ElasticCore()
        self.field_data = field_data
        self.indices = self.core.load_indices_from_field_data(field_data, indices)
        self.query = query
        self.scroll_size = scroll_size
        self.scroll_limit = scroll_limit
        self.ignore_ids = ignore_ids
        self.output = output
        self.callback_progress = callback_progress
        self.text_processor = text_processor

        if self.callback_progress:
            total_elements = self.count()
            callback_progress.set_total(total_elements)


    def __iter__(self):
        """
        Iterator for iterating through scroll
        """
        return self.scroll()


    def update_query(self, query):
        self.query = query
    

    def update_field_data(self, field_data):
        self.field_data = field_data


    def _parse_doc(self, doc):
        """
        Parses Elasticsearch hit into something nicer
        """
        parsed_doc, index = self._flatten_doc(doc)
        if self.field_data:
            path_list = [f['path'] for f in self.field_data]
            parsed_doc = {k:v for k,v in parsed_doc.items() if k in path_list}
        else:
            parsed_doc, _ = self._flatten_doc(doc)
        return parsed_doc


    def _flatten_doc(self, doc):
        """
        Flattens a document.
        """
        index = doc['_index']
        doc = doc['_source']
        new_doc = {}
        for field_name, field_content in doc.items():
            new_field_name, new_content = self._flatten_field(field_name, field_content)
            new_doc[new_field_name] = new_content
        return new_doc, index


    def _flatten_field(self, field_name, field_content):
        """
        Flattens a field.
        """
        if isinstance(field_content, dict):
            # go deeper
            for subfield_name, subfield_content in field_content.items():
                current_field_name = f'{field_name}.{subfield_name}'
                return self._flatten_field(current_field_name, subfield_content) 
        else:
            # this is the end
            return field_name, field_content


    def _decode_doc(self, doc, field_path=None):
        decoded_text = doc['_source']
        if field_path:
            # decode if field path known
            for k in field_path.split('.'):
                # get nested fields encoded as: 'field.sub_field'
                try:
                    decoded_text = decoded_text[k]
                except:
                    decoded_text = ""
        else:
            pass
        return decoded_text


    def count(self):
        response = self.core.es.search(index=self.indices, body=self.query)
        return response['hits']['total']


    def search(self, size=10):
        response = self.core.es.search(index=self.indices, body=self.query, size=size)
        if self.output == self.OUT_DOC:
            return [self._parse_doc(doc) for doc in response['hits']['hits']]
        else:
            return response


    def scroll(self):
        page = self.core.es.search(index=self.indices, body=self.query, scroll='1m', size=self.scroll_size)
        scroll_id = page['_scroll_id']
        current_page = 0

        page_size = len(page['hits']['hits'])
        num_scrolled = 0
        while page_size > 0:
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
                                parsed_doc = {k: '\n'.join(self.text_processor.process(v)) for k, v in parsed_doc.items()}
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

