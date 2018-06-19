#-*- coding: utf-8 -*-
import json
import logging
import numpy as np

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE, MDS
from sklearn.metrics.pairwise import pairwise_distances

from conceptualiser.models import Term, TermConcept, Concept
from lm.models import Word, Lexicon
from lm.views import model_manager
from task_manager.models import Task
from utils.datasets import Datasets

from texta.settings import STATIC_URL, URL_PREFIX, INFO_LOGGER

@login_required
def index(request):
    template = loader.get_template('conceptualiser.html')

    lexicons = []
    for lexicon in Lexicon.objects.all().filter(author=request.user):
        setattr(lexicon,'size',Word.objects.all().filter(lexicon=lexicon.id).count())
        lexicons.append(lexicon)

    methods = ["PCA","TSNE","MDS"]

    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type='train_model').filter(status='completed').order_by('-pk')
    
    return HttpResponse(template.render({'STATIC_URL':STATIC_URL,'lexicons':lexicons,'methods':methods, 'language_models': language_models, 'allowed_datasets': datasets},request))

@login_required
def load_ontology_by_id(request):
    dendro_id = request.GET['dendro_id']
    pass


@login_required
def load_terms(request):    

    lexicon_ids = json.loads(request.POST['lids'])

    try:
        model = model_manager.get_model(request.session['model']).model
    except LookupError as e:
        return HttpResponseRedirect(URL_PREFIX + '/')

    if model.wv.syn0norm is None:
        model.init_sims()

    words = [word for word in Word.objects.filter(lexicon__id__in = lexicon_ids) if word.wrd in model.wv.vocab]
    feature_vectors = [model.wv.syn0norm[model.wv.vocab[word.wrd].index] for word in words]
    
    output = {'terms':[],'concepts':[]}
    
    if len(feature_vectors):
        X = np.array(feature_vectors)

        if request.POST['method'] == 'TSNE':
            transformer = TSNE(n_components=2, random_state=0,metric='cosine',learning_rate=50)
        elif request.POST['method'] == 'MDS':
            transformer = MDS(n_components=2, max_iter=600,dissimilarity="precomputed", n_jobs=1)
            X = pairwise_distances(X,metric='cosine',n_jobs=1)
        else:
            transformer = PCA(n_components=2)

        transformed_feature_vectors = transformer.fit_transform(X).tolist()
        
        terms = []
        concepts = {}
        
        for i in range(len(words)):
            term = {'id':words[i].id,'term':words[i].wrd,'count':model.wv.vocab[words[i].wrd].count,'x':transformed_feature_vectors[i][0] if len(feature_vectors) > 1 else 0,'y':transformed_feature_vectors[i][1] if len(feature_vectors) > 1 else 0}
            
            term_concepts = TermConcept.objects.filter(term__term = words[i].wrd).filter(concept__author = request.user)
            if term_concepts:
                concept_id = term_concepts[0].concept.id
                descriptive_term = term_concepts[0].concept.descriptive_term.term
                descriptive_term_id = term_concepts[0].concept.descriptive_term.id
                if concept_id not in concepts:
                    concepts[concept_id] = {'id':concept_id,'terms':[],'descriptive_term':descriptive_term,'descriptive_term_id':Word.objects.filter(wrd=descriptive_term)[0].id}

                concepts[concept_id]['terms'].append(term)
                
            else:
                terms.append(term)
        
        output['terms'].extend(terms)
        output['concepts'].extend([concepts[concept_id] for concept_id in concepts])

        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE CONCEPTS','event':'terms_loaded','args':{'user_name':request.user.username,'lexicon_ids':lexicon_ids,'dim_red_method':request.POST['method']}}))
    else:
        logging.getLogger(INFO_LOGGER).warning(json.dumps({'process':'CREATE CONCEPTS','event':'term_loading_failed','args':{'user_name':request.user.username,'lexicon_ids':lexicon_ids,'dim_red_method':request.POST['method']},'reason':'No terms to load.'}))


    return HttpResponse(json.dumps(output), content_type='application/json')

@login_required
def get_term_lexicons(request):
    term_lexicons = Term.objects.all().filter(author=request.user)
    json = []
    for term_lexicon in term_lexicons:
        json.append({'id':term_lexicon.id,'name':term_lexicon.name})
    return HttpResponse(json, content_type='application/json')

@login_required
def get_ontologies(request):
    pass

@login_required
def get_lexicons(request):
    lexicons = Lexicon.objects.filter(author=request.user)
    output = [{'id':lex.id,'name':lex.name,'desc':lex.description} for lex in lexicons]
    
    logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE CONCEPTS','event':'lexicons_queried','args':{'user_name':request.user.username}}))
    
    return HttpResponse(json.dumps(output), content_type='application/json')

@login_required
def save_concepts(request):
    raw_concepts = json.loads(request.POST['concepts'])
    
    terms = []
    concepts = []
    id_mapping = []
    
    new_concepts = 0
    
    for raw_concept in raw_concepts:
        concept_words = {word.id:word for word in Word.objects.filter(id__in = raw_concept['term_ids'])}
        current_terms = {concept_words[concept_word_id].wrd:Term(is_internal=True,term=concept_words[concept_word_id].wrd,author=request.user) if not Term.objects.filter(term=concept_words[concept_word_id].wrd).filter(author=request.user).exists() else Term.objects.filter(term=concept_words[concept_word_id].wrd).filter(author=request.user)[0] for concept_word_id in concept_words}
        term_id_2_term = {}
        for term in current_terms:
            if not current_terms[term].id:
                current_terms[term].save()
            term_id_2_term[current_terms[term].id] = current_terms[term]

        terms.extend(current_terms.values())
        
        existing_concepts = Concept.objects.filter(descriptive_term__term = concept_words[raw_concept['descriptive_term_id']].wrd).filter(author=request.user)
        if existing_concepts.exists():
            concepts.append(existing_concepts[0])
        else:
            new_concept = Concept(descriptive_term=current_terms[concept_words[raw_concept['descriptive_term_id']].wrd], semantic_type='BASE_CONCEPT', author=request.user)
            new_concept.save()
            concepts.append(new_concept)
            new_concepts += 1
        
        id_mapping.append((len(terms)-len(concept_words),len(terms)))
    
    termconcepts_to_create = []
    for concept_idx in range(len(id_mapping)):
        for term_idx in range(id_mapping[concept_idx][0],id_mapping[concept_idx][1]):
            existing_termconcept = TermConcept.objects.filter(term=terms[term_idx])
            if existing_termconcept.exists():
                existing_termconcept.update(concept=concepts[concept_idx])
            else:
                termconcepts_to_create.append(TermConcept(term=terms[term_idx],concept=concepts[concept_idx]))
    
    step = 100
    i = 0
    while i < len(termconcepts_to_create):
        TermConcept.objects.bulk_create(termconcepts_to_create[i:i+step])
        i += step
    
    term_ids = json.loads(request.POST['terms'])
    term_words = Word.objects.filter(id__in = term_ids)
    term_labels = [word.wrd for word in term_words]
    
    Term.objects.filter(term__in = term_labels).delete()

    logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE CONCEPTS','event':'concepts_saved','args':{'user_name':request.user.username},'data':{'new_terms':len(termconcepts_to_create) ,'new_concepts':new_concepts}}))

    return HttpResponse()
