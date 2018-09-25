""" The Mass Helper class
"""

MAX_DOCS_PAGE = 5000


class MassHelper:
    """ Mass Helper Class

    Provides helper functionality to mass trainer and tagger
    """

    def __init__(self, es_manager):
        self.es_m = es_manager
        self.es_url = es_manager.es_url
        self.index = es_manager.index

    def _iterate_docs(self, q):
        """ Iterage over all docs for a given query q
        """
        # scroll
        resp = self.es_m.requests.get('{}/{}/_search?scroll=1m'.format(self.es_url, self.index), json=q)
        data = resp.json()
        scroll_id = data['_scroll_id']
        docs = data['hits']['hits']
        while docs:
            # Consume all page docs
            for d in docs:
                yield d
            # Next page
            resp = self.es_m.requests.get('{}/_search/scroll'.format(self.es_url),
                                          json={'scroll': '1m', 'scroll_id': scroll_id})
            data = resp.json()
            scroll_id = data['_scroll_id']
            docs = data['hits']['hits']

    def _get_total(self, q):
        """ Total of documents for a given query q
        """
        resp = self.es_m.requests.get('{}/{}/_count'.format(self.es_url, self.index), json=q)
        data = resp.json()
        total = data['count']
        return total

    def _dict_query_tag_filter(self, tag):
        q = {}
        q['query'] = {}
        q['query']['nested'] = {}
        q['query']['nested']['path'] = "texta_facts"
        q['query']['nested']['query'] = {'term': {"texta_facts.str_val": tag}}
        return q

    def get_unique_tags(self):
        """ Get Unique Tags
        """
        q = {}
        q['query'] = {}
        q['query']['nested'] = {}
        q['query']['nested']['path'] = "texta_facts"
        q['query']['nested']['query'] = {'term': {"texta_facts.fact": "TEXTA_TAG"}}
        q['_source'] = "texta_facts"
        q['size'] = MAX_DOCS_PAGE
        # Get unique tags
        unique_tags = set()
        for doc in self._iterate_docs(q):
            for f in doc['_source']['texta_facts']:
                if f['fact'] == 'TEXTA_TAG':
                    tag = f['str_val']
                    unique_tags.add(tag)
        return unique_tags

    def get_tag_frequency(self, tags):
        """ Get Tags frequency
        """
        tag_freq = {}
        for tag in tags:
            q = self._dict_query_tag_filter(tag)
            c = self._get_total(q)
            tag_freq[tag] = c
        return tag_freq
