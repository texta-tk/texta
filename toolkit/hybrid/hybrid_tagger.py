from toolkit.tagger.text_tagger import TextTagger
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.query import Query, QueryFilter

from  toolkit.tagger.models import Tagger

class HybridTagger:

    def __init__(self, tagger_ids=[], hybrid_filtering=True):
        self.elasticsearcher = ElasticSearcher()
        self.tagger_ids = tagger_ids
        self.taggers = list(self._load_taggers(self.tagger_ids))


    def _prepare_mlt_queries(self, text):
        """
        Creates separate query for each index with proper field names.
        """
        for index,fields in self.elasticsearcher.field_data.items():
            # should review this - maybe can use index?
            query = Query()
            query.add_mlt(fields, text)
            yield query


    @staticmethod
    def _load_taggers(tagger_ids):
        for tagger_id in tagger_ids:
            tagger = TextTagger(tagger_id)
            tagger.load()
            yield tagger


    def _filter_taggers(self, text):
        # retrive tagger objects and labels
        tagger_objects = Tagger.objects.filter(pk__in=self.tagger_ids)
        tagger_labels = [tagger_obj.description for tagger_obj in tagger_objects]

        # retrieve & decode field data
        field_data = [tagger_obj.fields for tagger_obj in tagger_objects]
        field_data = [self.elasticsearcher.core.decode_field_data(item) for sublist in field_data for item in sublist]

        # create new instance with proper field data
        self.elasticsearcher = ElasticSearcher(field_data=field_data, output='doc')

        # create mlt queries to find similar documents
        queries = list(self._prepare_mlt_queries(text))
        
        for query in queries:
            self.elasticsearcher.update_query(query.query)
            search_result = self.elasticsearcher.search(size=30)

            # filter out tags here
            print([a.keys() for a in search_result])


    def tag_text(self, text):

        #filter taggers
        self._filter_taggers(text)

        tags = []
        for tagger in self.taggers:
            tagger_response = tagger.tag_text(text)
            if tagger_response[0]:
                tags.append(tagger.description)

        return tags
    

    def tag_doc(self, text):
        pass
