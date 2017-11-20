from conceptualiser.models import Term, TermConcept
from lm.models import Lexicon
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

class Autocomplete:

    def __init__(self):
        self.es_m = None        
        self.lookup_type = None
        self.content = None
        self.user = None
        self.limit = None

    def parse_request(self,request):
        self.lookup_types = request.POST['lookup_types'].split(',')
        self.content = request.POST['content'].split('\n')[-1].strip()
        
        ds = Datasets().activate_dataset(request.session)
        self.dataset = ds.get_index()
        self.mapping = ds.get_mapping()
        self.es_m = ES_Manager(self.dataset, self.mapping)

        self.user = request.user

    def suggest(self,limit=10):
        self.limit = limit
        
        suggestions = {}

        for lookup_type in self.lookup_types:
            if lookup_type == 'FACT_NAME':
                suggestions['FACT_NAME'] = self._get_facts('fact')
            elif lookup_type == 'FACT_VAL':
                suggestions['FACT_VAL'] = self._get_facts('str_val')
            elif lookup_type == 'CONCEPT':
                suggestions['CONCEPT'] = self._get_concepts()
            elif lookup_type == 'LEXICON':
                suggestions['LEXICON'] = self._get_lexicons()
        
        return suggestions

    def _get_facts(self,agg_subfield):
        agg_query = {
                agg_subfield: {
                    "nested": {"path": "texta_facts"},
                    "aggs": {
                        agg_subfield: {
                            "terms": {"field": "texta_facts.{0}".format(agg_subfield), "size": self.limit, "include": "{0}.*".format(self.content.encode('utf8'))},
                        }
                    }
                }
            }

        self.es_m.build('')
        self.es_m.set_query_parameter("aggs", agg_query)
        
        facts = [self._format_suggestion(a["key"],a["key"]) for a in self.es_m.search()["aggregations"][agg_subfield][agg_subfield]["buckets"]]

        return facts

    def _get_concepts(self):
        concepts = []

        if len(self.content) > 0:
            terms = Term.objects.filter(term__startswith=self.content).filter(author=self.user)
            seen = {}
            for term in terms[:self.limit]:
                for term_concept in TermConcept.objects.filter(term=term.pk):
                    concept = term_concept.concept
                    concept_term = (concept.pk,term.term)

                    if concept_term not in seen:
                        seen[concept_term] = True

                        display_term = term.term.replace(self.content,'<font color="red">'+self.content+'</font>')
                        display_text = '<b>{0}</b>@C{1}-{2}'.format(display_term.encode('utf8'),concept.pk,concept.descriptive_term.term.encode('utf8'))

                        suggestion = self._format_suggestion(concept.descriptive_term.term,display_text,resource_id=concept.pk)
                        concepts.append(suggestion)
        
        return concepts

    def _get_lexicons(self):
        suggested_lexicons = []

        if len(self.content) > 0:
            lexicons = Lexicon.objects.filter(name__startswith=self.content).filter(author=self.user)
            for lexicon in lexicons:
                display_term = lexicon.name.replace(self.content,'<font color="red">'+self.content+'</font>')
                display_text = '<b>{0}</b>@L{1}-{2}'.format(display_term.encode('utf8'),lexicon.pk,lexicon.name.encode('utf8'))

                suggestion = self._format_suggestion(lexicon.name,display_text,resource_id=lexicon.pk)
                suggested_lexicons.append(suggestion)
                
        return suggested_lexicons

    @staticmethod
    def _format_suggestion(entry_text,display_text,resource_id=''):
        return {'entry_text':entry_text,'display_text':display_text,'resource_id':resource_id}
