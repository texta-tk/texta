#-*- coding:utf-8 -*-
import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import loader

from conceptualiser.models import Concept, Term, TermConcept
from lexicon_miner.models import Lexicon
from task_manager.models import Task
from utils.datasets import Datasets
from task_manager.tasks.task_types import TaskTypes

from texta.settings import STATIC_URL

@login_required
def index(request):
    template = loader.get_template('ontology_viewer.html')
    overview_data = [('Base lexicons created',str(len(Lexicon.objects.filter(author=request.user)))),
                     ('Concepts commited',str(len(Concept.objects.filter(author=request.user))))]

    datasets = Datasets().get_allowed_datasets(request.user)
    language_models =Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL.value).filter(status__iexact='completed').order_by('-pk')

    return HttpResponse(template.render({'STATIC_URL':STATIC_URL,'overview_data':overview_data,'language_models': language_models, 
                                         'allowed_datasets': datasets},request))

@login_required
def get_concepts(request):
    concepts = Concept.objects.filter(author=request.user)
    return HttpResponse(json.dumps([{'id':concept.id,'name':concept.descriptive_term.term} for concept in concepts]))

@login_required   
def get_concept_terms(request):
    concept_id = int(request.GET['cid'])
    concept = Concept.objects.get(id=concept_id)
    term_concepts = TermConcept.objects.filter(concept=concept)
    return HttpResponse(json.dumps([{'id':term_concept.term.id,'term':term_concept.term.term} for term_concept in term_concepts]))

def delete_term(request):
   term_id = int(request.GET['id'])
   Term.objects.get(id=term_id).delete()
   return HttpResponse(term_id)

def delete_concept(request):
    concept_id = int(request.GET['id'])
    Concept.objects.get(id=concept_id).delete()
    return HttpResponse(concept_id)
