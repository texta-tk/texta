import collections
from typing import List

import elasticsearch
from elasticsearch_dsl.query import MoreLikeThis
from elasticsearch_dsl import Search

from toolkit.elastic.core import ElasticCore


ES_SCROLL_SIZE = 500
EMPTY_QUERY = {"query": {"match_all": {}}}


class ElasticSearcher:
    """
    Everything related to performing searches in Elasticsearch
    """
    OUT_RAW = 'raw'
    OUT_DOC = 'doc'
    OUT_TEXT = 'text'
    OUT_TEXT_WITH_ID = "text_with_id"
    OUT_DOC_WITH_ID = 'doc_with_id'
    OUT_DOC_WITH_TOTAL_HL_AGGS = 'doc_with_total_hl_aggs'


    def __init__(self, field_data=[],
                 indices=[],
                 query=EMPTY_QUERY,
                 scroll_size=ES_SCROLL_SIZE,
                 output=OUT_DOC,
                 callback_progress=None,
                 scroll_limit=None,
                 ignore_ids=set(),
                 text_processor=None,
                 score_threshold=0.0,
                 timeout='10m'):
        """
        Output options: document (default), text (lowered & stopwords removed), sentences (text + line splitting), raw (raw elastic output)
        """
        self.core = ElasticCore()
        self.field_data: List[str] = field_data
        self.indices = indices
        self.query = query
        self.scroll_size = scroll_size
        self.scroll_limit = scroll_limit
        self.score_threshold = score_threshold
        self.ignore_ids = ignore_ids
        self.output = output
        self.callback_progress = callback_progress
        self.text_processor = text_processor
        self.timeout = timeout

        if self.callback_progress:
            total_elements = self.count()
            if scroll_limit and scroll_limit < total_elements:
                total_elements = scroll_limit
            callback_progress.set_total(total_elements)


    def __iter__(self):
        """
        Iterator for iterating through scroll
        """
        return self.scroll()


    def more_like_this(self, mlt_fields: List[str], like, min_term_freq=1, max_query_terms=12, min_doc_freq=5, min_word_length=0, max_word_length=0, stop_words=[], size=10, include_meta=False, indices: str = None):
        """

        Args:
            indices: Coma-separated string of the indices you wish to use.
            mlt_fields: List of strings of the fields you wish to use for analyzation, only these fields are returned as a result.
            like: Can either be a text field or a list of document metas which is used as a baseline for fetching similar documents.
            min_term_freq: The minimum term frequency below which the terms will be ignored from the input document.
            max_query_terms: The maximum number of query terms that will be selected. Increasing this value gives greater accuracy at the expense of query execution speed.
            min_doc_freq: The minimum document frequency below which the terms will be ignored from the input document.
            min_word_length: The minimum word length below which the terms will be ignored.
            max_word_length: The maximum word length above which the terms will be ignored.
            stop_words: An array of stop words. Any word in this set is considered "uninteresting" and ignored.
            include_meta: Whether to add the documents meta information (id, index, doctype) into the returning set of documents.
            size: How many documents to return with the end result.
        Returns: List of Elasticsearch documents.

        """
        indices = indices if indices else ",".join(self.indices)
        s = Search(using=self.core.es, index=indices)
        mlt = MoreLikeThis(like=like, fields=mlt_fields, min_term_freq=min_term_freq, max_query_terms=max_query_terms, min_doc_freq=min_doc_freq, min_word_length=min_word_length, max_word_length=max_word_length, stop_words=stop_words)
        s = s.query(mlt)
        s = s.extra(size=size)
        s = s.source(mlt_fields)
        if include_meta:
            response = [{"_id": hit.meta.id, "_type": hit.meta.doc_type, "_index": hit.meta.index, "_source": hit.to_dict()} for hit in s.execute()]
            return response
        else:
            response = [hit.to_dict() for hit in s.execute()]
            return response



    def update_query(self, query):
        self.query = query


    def update_field_data(self, field_data):
        self.field_data = field_data


    def _parse_doc(self, doc):
        """
        Parses Elasticsearch hit into something nicer
        """
        parsed_doc, _, _ = self._flatten_doc(doc)
        if self.field_data:
            parsed_doc = {k: v for k, v in parsed_doc.items() if self.field_data.count(k)}
        else:
            parsed_doc, _, _ = self._flatten_doc(doc)
        return parsed_doc


    def _parse_doc_with_highlight(self, doc):
        """
        Parses Elasticsearch hit into something nicer, includes the highlight field
        """
        parsed_doc, _, highlight = self._flatten_doc(doc)
        return {'highlight': highlight, 'doc': parsed_doc}


    def _flatten_doc(self, doc):
        """
        Flattens a document.
        """
        index = doc['_index']
        highlight = doc['highlight'] if 'highlight' in doc else {}
        doc = doc['_source']
        new_doc = self._flatten(doc)
        return new_doc, index, highlight


    def _flatten(self, d, parent_key='', sep='.'):
        """
        From: https://stackoverflow.com/questions/6027558/flatten-nested-dictionaries-compressing-keys
        """
        items = []
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if isinstance(v, collections.MutableMapping):
                items.extend(self._flatten(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)


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


    def count(self) -> int:
        try:
            count = self.core.es.count(index=self.indices, body=self.query)
            return count["count"]
        except elasticsearch.NotFoundError:
            return 0


    def search(self, size=10):
        # In case size/from is included in query in pagination, don't overwrite it by passing the size parameter
        if 'size' in self.query:
            response = self.core.es.search(index=self.indices, body=self.query, timeout=self.timeout)
        else:
            response = self.core.es.search(index=self.indices, body=self.query, size=size, timeout=self.timeout)
        if self.output == self.OUT_DOC:
            hits = [self._parse_doc(doc) for doc in response['hits']['hits']]
            return hits
        if self.output == self.OUT_DOC_WITH_TOTAL_HL_AGGS:
            return {
                'count': response['hits']['total'],
                'aggs': response['aggregations'] if 'aggregations' in response else {},
                'results': [self._parse_doc_with_highlight(doc) for doc in response['hits']['hits']]
            }

        else:
            return response


    def random_documents(self, size=10):
        """
        Returns n random documents, where n=size.
        """
        random_query = {"query": {"function_score": {"query": {"match_all": {}}, "functions": [{"random_score": {}}]}}}
        response = self.core.es.search(index=self.indices, body=random_query, size=size)
        if self.output == self.OUT_DOC:
            return [self._parse_doc(doc) for doc in response['hits']['hits']]
        else:
            return response


    # batch search makes an inital search, and then keeps pulling batches of results, until none are left.
    def scroll(self):
        page = self.core.es.search(index=self.indices, body=self.query, scroll=self.timeout, size=self.scroll_size)
        scroll_id = page['_scroll_id']
        current_page = 0
        # set page size
        page_size = len(page['hits']['hits'])
        num_scrolled = 0
        # set score threshold
        if page['hits']['max_score']:
            lowest_allowed_score = page['hits']['max_score'] * self.score_threshold
        else:
            lowest_allowed_score = self.score_threshold
        # set scroll break default
        scroll_break = False
        # iterate through scroll
        while page_size > 0:
            # break scroll is asked
            if scroll_break:
                break
            # process output
            if self.output in (self.OUT_DOC, self.OUT_DOC_WITH_ID, self.OUT_TEXT, self.OUT_TEXT_WITH_ID):
                if self.callback_progress:
                    self.callback_progress.update(page_size)
                for hit in page['hits']['hits']:
                    # if scroll limit reached, break the scroll
                    if self.scroll_limit and num_scrolled >= self.scroll_limit:
                        scroll_break = True
                        break
                    # if score too low, break scroll
                    elif hit['_score'] < lowest_allowed_score:
                        scroll_break = True
                        break
                    if hit['_id'] not in self.ignore_ids:
                        num_scrolled += 1
                        parsed_doc = self._parse_doc(hit)
                        if self.output == self.OUT_TEXT:
                            for field in parsed_doc.values():
                                processed_field = self.text_processor.process(field)
                                for text in processed_field:
                                    yield text

                        elif self.output == self.OUT_TEXT_WITH_ID:
                            for key, value in parsed_doc.items():
                                if key in self.field_data:
                                    processed_field = self.text_processor.process(value)
                                    for text in processed_field:
                                        yield hit["_id"], text


                        elif self.output in (self.OUT_DOC, self.OUT_DOC_WITH_ID):
                            if self.text_processor:
                                parsed_doc = {k: '\n'.join(self.text_processor.process(v)) for k, v in parsed_doc.items()}
                            if self.output == self.OUT_DOC_WITH_ID:
                                parsed_doc['_id'] = hit['_id']
                            yield parsed_doc
            # return raw hit
            elif self.output == self.OUT_RAW:
                # filter page by score
                page = [doc for doc in page["hits"]["hits"] if doc['_score'] > lowest_allowed_score]
                # if score too low, break scroll
                if not page:
                    scroll_break = True
                    break
                # filter by ignored ids
                page = [doc for doc in page if doc['_id'] not in self.ignore_ids]
                if page:
                    num_scrolled += len(page)
                    yield page

            # get new page
            page = self.core.es.scroll(scroll_id=scroll_id, scroll=self.timeout)
            scroll_id = page['_scroll_id']
            page_size = len(page['hits']['hits'])
            current_page += 1
