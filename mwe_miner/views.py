# -*- coding: utf8 -*-
from __future__ import print_function
import itertools
import json
import logging
from datetime import datetime

import platform
if platform.system() == 'Windows':
    from threading import Thread as Process
else:
    from multiprocessing import Process

import requests
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader

from conceptualiser.models import Term,TermConcept,Concept
from lm.models import Lexicon,Word
from mwe_miner.models import Run
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import URL_PREFIX, STATIC_URL, es_url, INFO_LOGGER, ERROR_LOGGER


@login_required
def index(request):
    template = loader.get_template('mwe_miner.html')
    lexicons = []
    runs = []
    for run in  Run.objects.all().filter(user=request.user).order_by('-pk'):
        try:
            groups = json.loads(run.results).values()
            num_mwes = sum(len(group['mwes']) for group in groups)
            setattr(run,'num_groups',len(groups))
            setattr(run,'num_mwes',num_mwes)
        #        setattr(run,'committed',len({approved_candidate.candidate for approved_candidate in approved_term_candidates} & {committed_candidate.term for committed_candidate in Term.objects.filter(author=request.user)}))
        except ValueError as e:
            print('Exception', e)
            pass
        runs.append(run)
    for lexicon in Lexicon.objects.all().filter(author=request.user):
        setattr(lexicon,'size',Word.objects.all().filter(lexicon=lexicon.id).count())
        lexicons.append(lexicon)

    # Define selected mapping
    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)
    fields = es_m.get_column_names()

    return HttpResponse(template.render({'lexicons':lexicons,'STATIC_URL':STATIC_URL,'runs':runs,'fields':fields},request))

@login_required
def results(request):
    template = loader.get_template('mwe_results.html')
    run_id  = request.GET['run_id']
    results = json.loads(Run.objects.get(pk=run_id).results)
    results = sorted([results[key] for key in results],key=lambda x: x[u'total_freq'],reverse=True)
    out = []
    for group in results:
        children_ids = []
        for mwe in group['mwes']:
            children_ids.append(mwe['id'])
        group['mwe_ids'] = children_ids
        out.append(group)
    return HttpResponse(template.render({'results':out,'run_id':run_id,'STATIC_URL':STATIC_URL},request))

@login_required
def delete_result(request):
    try:
        run_id  = request.GET['run_id']
        run = Run.objects.get(pk=run_id)
        run.delete()
        
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'DELETE MWE RESULT','event':'mwe_result_deleted','args':{'user_name':request.user.username,'run_id':run_id}}))
    except Exception as e:
        print(e)
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'DELETE MWE RESULT','event':'mwe_result_deletion_failed','args':{'user_name':request.user.username,'run_id':run_id}}),exc_info=True)
        
    return HttpResponseRedirect(URL_PREFIX + '/mwe_miner')

@login_required
def approve(request):
    try:
        operator = request.POST['operator']
        run_id = request.POST['run_id']
        results = json.loads(Run.objects.get(pk=run_id).results)
        ticked = [int(a) for a in request.POST.getlist('approved[]')]
        if operator == 'reverse':
            for key,group in results.items():
                i=0
                
                for mwe in group['mwes']:
                    if mwe['id'] in ticked:
                        if results[key]['mwes'][i]['accepted'] == False:
                            concept_term_name = group['concept_name']['label']
                            concepts = Concept.objects.filter(descriptive_term__term = concept_term_name).filter(author = request.user)
                            
                            results[key]['mwes'][i]['accepted'] = True
                            
                            new_term = Term(is_internal=True,term=mwe['mwe'],author=request.user)
                            new_term.save()
                            
                            if concepts.exists():
                                concept = concepts[0]
                                
                                if mwe['freq'] > results[key]['concept_name']['freq']:
                                    results[key]['concept_name'] = {'freq':mwe['freq'],'label':mwe['mwe']}
                                    concept_term_name = group['concept_name']['label']
                                    concept.descriptive_term = new_term
                            else:
                                concept = Concept(descriptive_term=new_term,semantic_type='',author=request.user)
                                results[key]['concept_name'] = {'freq':mwe['freq'],'label':mwe['mwe']}
                            
                            concept.save()
                            
                            term_concept = TermConcept(term=new_term,concept=concept)
                            term_concept.save()
                            
                        else:
                            concept_term_name = group['concept_name']['label']
                            concepts = Concept.objects.filter(descriptive_term__term = concept_term_name).filter(author = request.user)
                            results[key]['mwes'][i]['accepted'] = False

                            concept = concepts[0]
                            
                            if mwe['mwe'] == concept_term_name:
                                term_concepts = TermConcept.objects.filter(concept=concept)
                                if len(term_concepts) == 1:
                                    Term.objects.filter(term=mwe['mwe']).filter(author=request.user)[0].delete() # removing concept alongside
                                    results[key]['concept_name'] = {'freq':-1,'label':''}
                                    
                                else:
                                    # replace to-be-removed term in concept with the next most frequent approved term
                                    most_freq_term = max([x for x in group['mwes'] if x['accepted'] == True],key=lambda x: x['freq'])
                                    concept.descriptive_term = Term.objects.filter(term=most_freq_term['mwe']).filter(author=request.user)[0]
                                    concept.save()
                                    results[key]['concept_name'] = {'freq':most_freq_term['freq'],'label':most_freq_term['mwe']}
                                    
                                    Term.objects.filter(term=mwe['mwe']).filter(author=request.user)[0].delete()

                            else:    
                                term = Term.objects.filter(term=mwe['mwe']).filter(author=request.user)[0]
                                term.delete()                     
                            
                    i+=1
        else:
            for key,group in results.items():
                i=0
                if operator == 'alltrue':
                    # Set term corresponding to display_name to be the descriptive_term for the group as a concept
                    term, created = Term.objects.get_or_create(term=results[key]['display_name']['label'],author=request.user,defaults={'is_internal':True})
                    
                    if results[key]['concept_name']['label']:
                        concept = Concept.objects.get(descriptive_term=Term.objects.get(term=results[key]['concept_name']['label'],author=request.user))
                    else:
                        concept = Concept(descriptive_term=term,semantic_type="",author=request.user)
                        concept.save()
                    
                    if created:
                        concept.descriptive_term = term
                        concept.save()
                        TermConcept(term=term,concept=concept).save()
                        results[key]['concept_name']['label'] = {'label':results[key]['display_name']['label'],'freq':results[key]['display_name']['freq']}
                    
                for mwe in group['mwes']:
                    group['concept_name'] = {'label':'','freq':-1}
                    if operator == 'alltrue':
                        results[key]['mwes'][i]['accepted'] = True
                        term, created = Term.objects.get_or_create(term=results[key]['mwes'][i]['mwe'],author=request.user,defaults={'is_internal':True})
                        if created:
                            TermConcept.objects.create(term=term,concept=concept)
                    else:
                        results[key]['mwes'][i]['accepted'] = False
                        Term.objects.filter(term=results[key]['mwes'][i]['mwe']).filter(author=request.user).delete()
                    i+=1
        r = Run.objects.get(pk=run_id)
        r.results = json.dumps(results)
        r.save()
        
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'APPROVE MWE RESULT','event':'mwe_result_items_approved','args':{'user_name':request.user.username,'operator':operator,'run_id':run_id}}))
    except Exception as e:
        print(e)
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'APPROVE MWE RESULT','event':'mwe_result_item_approval_failed','args':{'user_name':request.user.username,'operator':operator,'run_id':run_id}}),exc_info=True)

    return HttpResponse()

@login_required
def commit(request):
    run_id = request.GET['run_id']
    #TODO Misasi on TermCandidate? KOM teab?
    approved_term_candidates = TermCandidate.objects.filter(run__pk = run_id).filter(approved=True)
    committed_candidates = Term.objects.filter(author=request.user)
    new_approved_term_candidate_strs = {approved_candidate.candidate for approved_candidate in approved_term_candidates} - {committed_candidate.term for committed_candidate in committed_candidates}
    terms = [Term(is_internal=True,term=new_term_str, author=request.user) for new_term_str in new_approved_term_candidate_strs]
    Term.objects.bulk_create(terms)
    return HttpResponseRedirect(URL_PREFIX + '/mwe_miner')

@login_required
def start_mapping_job(request):
    Process(target=find_mappings,args=(request,)).start()
    return HttpResponse()

def flatten(container):
    for i in container:
        if isinstance(i, list) or isinstance(i, tuple):
            for j in flatten(i):
                yield j
        else:
            yield i

def conceptualise_phrase(phrase,usr):
    new_phrase = []
    for word in phrase.split(' '):
        try:
            concept = TermConcept.objects.filter(term=Term.objects.filter(term=word,author_id=usr.pk)[0])[0].concept
            concept_id = 'CID_'+str(concept.pk)
            new_phrase.append(concept_id)
        except IndexError:
            new_phrase.append(word)
    return ' '.join(sorted(new_phrase))

def find_mappings(request):
    try:
        slop     = int(request.POST['slop'])
        max_len  = int(request.POST['max_len'])
        min_len  = int(request.POST['min_len'])
        min_freq = int(request.POST['min_freq'])
        match_field = request.POST['match_field']
        description = request.POST['description']

        batch_size = 50

        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        dataset = ds.get_index()
        mapping = ds.get_mapping()

        lexicon = []
        word_index = {}
        num_lexicons = 0
        for i,lexicon_id in enumerate(request.POST.getlist('lexicons[]')):
            num_lexicons +=1
            for word in Word.objects.filter(lexicon=lexicon_id):
                word = word.wrd
                lexicon.append(word)
                if word not in word_index:
                    word_index[word] = []
                word_index[word].append(i)
        lexicon = list(set(lexicon))
        if min_len > num_lexicons:
            min_len = num_lexicons
        mwe_counter = 0
        group_counter = 0
        phrases = []
        final   = {}
        data = []
        new_run = Run(minimum_frequency=min_freq,maximum_length=max_len,minimum_length=min_len,run_status='running',run_started=datetime.now(),run_completed=None,user=request.user,description=description)
        new_run.save()
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'MINE MWEs','event':'mwe_mining_started','args':{'user_name':request.user.username,'run_id':new_run.id,'slop':slop,'min_len':min_len,'max_len':max_len,'min_freq':min_freq,'match_field':match_field,'desc':description}}))
        for i in range(min_len,max_len+1):
            print('Permutation len:',i)
            for permutation in itertools.permutations(lexicon,i):
                word_indices = list(flatten([word_index[word] for word in permutation])) 
                if len(word_indices) == len(set(word_indices)):
                    permutation = ' '.join(permutation)
                    if slop > 0:
                        query = {"query": {"match_phrase": {match_field: {"query": permutation,"slop": slop}}}}
                    else:
                        query = {"query": {"match_phrase": {match_field: {"query": permutation}}}}
                    data.append(json.dumps({"index":dataset,"mapping":mapping})+'\n'+json.dumps(query))
                    phrases.append(permutation)
                    if len(data) == batch_size:
                        for j,response in enumerate(ES_Manager.plain_multisearch(es_url, dataset, mapping, data)):
                            try:
                                if response['hits']['total'] >= min_freq:
                                    sorted_phrase = ' '.join(sorted(phrases[j].split(' ')))
                                    sorted_conceptualised_phrase = conceptualise_phrase(sorted_phrase,request.user)
                                    if sorted_conceptualised_phrase not in final:
                                        final[sorted_conceptualised_phrase] = {'total_freq':0,'mwes':[],'display_name':{'freq':0,'label':False},'id':group_counter}
                                        group_counter+=1
                                    final[sorted_conceptualised_phrase]['total_freq']+=response['hits']['total']
                                    final[sorted_conceptualised_phrase]['mwes'].append({'mwe':phrases[j],'freq':response['hits']['total'],'accepted':False,'id':mwe_counter})
                                    mwe_counter+=1
                                    final[sorted_conceptualised_phrase]['mwes'].sort(reverse=True,key=lambda k: k['freq'])
                                    if response['hits']['total'] > final[sorted_conceptualised_phrase]['display_name']['freq']:
                                        final[sorted_conceptualised_phrase]['display_name']['freq'] = response['hits']['total']
                                        final[sorted_conceptualised_phrase]['display_name']['label'] = phrases[j]
                            except KeyError as e:
                                raise e
                        data = []
                        phrases = []
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'MINE MWEs','event':'mwe_mining_progress','args':{'user_name':request.user.username,'run_id':new_run.id},'data':{'permutations_processed':i+1-min_len,'total_permutations':max_len-min_len+1}}))
        
        m_response = ES_Manager.plain_multisearch(es_url, dataset, mapping, data)
        
        for j,response in enumerate(m_response):
            try:
                if response['hits']['total'] >= min_freq:
                    sorted_phrase = ' '.join(sorted(phrases[j].split(' ')))
                    sorted_conceptualised_phrase = conceptualise_phrase(sorted_phrase,request.user)
                    if sorted_conceptualised_phrase not in final:
                        final[sorted_conceptualised_phrase] = {'total_freq':0,'mwes':[],'display_name':{'freq':0,'label':False},'id':group_counter}
                        group_counter+=1
                    final[sorted_conceptualised_phrase]['total_freq']+=response['hits']['total']
                    final[sorted_conceptualised_phrase]['mwes'].append({'mwe':phrases[j],'freq':response['hits']['total'],'accepted':False,'id':mwe_counter})
                    mwe_counter+=1
                    final[sorted_conceptualised_phrase]['mwes'].sort(reverse=True,key=lambda k: k['freq'])
                    if response['hits']['total'] > final[sorted_conceptualised_phrase]['display_name']['freq']:
                        final[sorted_conceptualised_phrase]['display_name']['freq'] = response['hits']['total']
                        final[sorted_conceptualised_phrase]['display_name']['label'] = phrases[j]
            except KeyError as e:       
                raise e
        for key in final:
            final[key]['concept_name'] = {'freq':-1,'label':''}
        r = Run.objects.get(pk=new_run.pk)
        r.run_completed = datetime.now()
        r.run_status = 'completed'
        r.results =json.dumps(final)
        r.save()
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'MINE MWEs','event':'mwe_mining_completed','args':{'user_name':request.user.username,'run_id':new_run.id}}))
    except Exception as e:
        print(e)
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'MINE MWEs','event':'mwe_mining_failed','args':{'user_name':request.user.username,'run_id':new_run.id}}),exc_info=True)
