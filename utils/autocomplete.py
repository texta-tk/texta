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
                suggestions['FACT_NAME'] = self._get_fact_names()
            elif lookup_type == 'CONCEPT':
                suggestions['CONCEPT'] = self._get_concepts()
            elif lookup_type == 'LEXICON':
                suggestions['LEXICON'] = self._get_lexicons()
        
        return suggestions

    def _get_fact_names(self):
        agg_query = {
                "fact_names": {
                    "nested": {"path": "texta_facts"},
                    "aggs": {
                        "fact_names": {
                            "terms": {"field": "texta_facts.fact", "size": 0},
                            "aggs": {"documents": {"reverse_nested": {}}}
                        }
                    }
                }
            }

        self.es_m.build('')
        self.es_m.set_query_parameter("aggs", agg_query)
        fact_names = [self._format_suggestion(a["key"],a["key"]) for a in self.es_m.search()["aggregations"]["fact_names"]["fact_names"]["buckets"]]

        return fact_names
        
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
                        display_text = '<b>{0}</b>@C{1}-{2}'.format(display_term,concept.pk,concept.descriptive_term.term)

                        suggestion = self._format_suggestion(concept.descriptive_term.term,display_text,resource_id=concept.pk)
                        concepts.append(suggestion)
        
        return concepts

    def _get_lexicons(self):
        suggested_lexicons = []

        if len(self.content) > 0:
            lexicons = Lexicon.objects.filter(name__startswith=self.content).filter(author=self.user)
            for lexicon in lexicons:
                display_term = lexicon.name.replace(self.content,'<font color="red">'+self.content+'</font>')
                display_text = '<b>{0}</b>@L{1}-{2}'.format(display_term,lexicon.pk,lexicon.name)

                suggestion = self._format_suggestion(lexicon.name,display_text,resource_id=lexicon.pk)
                suggested_lexicons.append(suggestion)
                
        return suggested_lexicons

    @staticmethod
    def _format_suggestion(entry_text,display_text,resource_id=''):
        return {'entry_text':entry_text,'display_text':display_text,'resource_id':resource_id}
        

    """

    lookup_type = request.POST['lookup_type']
    field_name = request.POST['field_name']
    field_id = request.POST['id']
    content = request.POST['content']

    autocomplete_data = {}
    if 'autocomplete_data' in request.session:
        autocomplete_data = request.session['autocomplete_data']

    suggestions = []

    if (lookup_type in autocomplete_data) and (field_name in autocomplete_data[lookup_type].keys()):
        for term in autocomplete_data[lookup_type][field_name]:
            term = smart_str(term)
            insert_function = "insert('','{0}','{1}','{2}');".format(field_id, term, lookup_type)
            html_suggestion = '<li class="list-group-item" onclick="{0}">{1}</li>'.format(insert_function, term)
            suggestions.append(html_suggestion)
    else:

        last_line = content.split('\n')[-1] if content else ''

        if len(last_line) > 0:
            terms = Term.objects.filter(term__startswith=last_line).filter(author=request.user)
            seen = {}
            suggestions = []
            for term in terms[:10]:
                for term_concept in TermConcept.objects.filter(term=term.pk):
                    concept = term_concept.concept
                    concept_term = (concept.pk,term.term)
                    if concept_term not in seen:
                        seen[concept_term] = True
                        display_term = term.term.replace(last_line,'<font color="red">'+last_line+'</font>')
                        display_text = "<b>"+smart_str(display_term)+"</b> @"+smart_str(concept.pk)+"-"+smart_str(concept.descriptive_term.term)
                        suggestions.append("<li class=\"list-group-item\" onclick=\"insert('"+str(concept.pk)+"','"+str(field_id)+"','"+smart_str(concept.descriptive_term.term)+"');\">"+display_text+"</li>")

    """
