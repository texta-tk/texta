# -*- coding: utf8 -*-
import random
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.template import loader
import requests


from lm.models import Lexicon, Word, SuggestionSet
from model_manager.models import ModelRun
from utils.robust_rank_aggregation import aggregate_ranks
from utils.model_manager import get_model_manager
from utils.precluster import PreclusterMaker
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import URL_PREFIX, STATIC_URL, INFO_LOGGER, ERROR_LOGGER
from texta.settings import es_url, es_links


model_manager = get_model_manager(expiration_time=300,refresh_time=30)
punct_to_name = {'!': '___exclamation___', ' ': '______', '"': '___quot___', "'": '___apo___', ')': '___r_para___', '(': '___l_para___', '-': '___hyphen___', ',': '___comma___', '/': '___slash___', '.': '___period___', '\\': '___backslash___', ';': '___semicolon___', ':': '___colon___', ']': '___r_bracket___', '[': '___l_bracket___', '?': '___question___', '&':'___and___', '%':'___percentage___'}

def uniq(l):
    seen = {}
    for item in l:
        if item['word'] not in seen:
            seen[item['word']]=item
    return seen.values()

@login_required
def index(request):
    if 'model' not in request.session:
        return HttpResponseRedirect(URL_PREFIX + '/')
    template = loader.get_template('lm.html')
    lexicons = Lexicon.objects.all().filter(author=request.user)
    return HttpResponse(template.render({'lexicons':lexicons,'STATIC_URL':STATIC_URL},request))

@login_required
def newLexicon(request):
    lexiconName = request.POST['lexiconname']
    model_pk = int(request.session['model'])
    
    if lexiconName:
        try:
            Lexicon(name=lexiconName,description='na',author=request.user).save()
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE LEXICON','event':'lexicon_creation_failed','args':{'user_name':request.user.username,'lexicon_name':lexiconName}}),exc_info=True)
            
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'lexicon_created','args':{'user_name':request.user.username,'lexicon_name':lexiconName}}))
    
    return HttpResponseRedirect(URL_PREFIX + '/lm')

@login_required
def deleteLexicon(request):
    try:
        lexicon = Lexicon.objects.get(id=request.GET['id'])
        model_manager.remove_negatives(request.session['model'],request.user.username,lexicon.id)
        Word.objects.filter(lexicon=lexicon).delete()
        lexicon.delete()
    
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'lexicon_deleted','args':{'user_name':request.user.username,'lexicon_id':request.GET['id']}}))
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE LEXICON','event':'lexicon_deletion_failed','args':{'user_name':request.user.username,'lexicon_id':request.GET['id']}}),exc_info=True)
    
    return HttpResponseRedirect(URL_PREFIX + '/lm')

@login_required
def saveLexicon(request):
    lexId = request.POST['id']
    try:
        if lexId:
            lexicon = Lexicon.objects.get(id=lexId)
            Word.objects.filter(lexicon=lexicon).delete()

            model_manager.save_negatives(request.session['model'],request.user.username,lexicon.id)
            
            lexicon_words = uniq(json.loads(request.POST['lexicon']))
            suggestionset_map = {}
            for lexicon_word in lexicon_words:
                if lexicon_word['sid'] >= 0:
                    suggestionset_map[lexicon_word['word']]=SuggestionSet.objects.get(id=lexicon_word['sid'])
            
            step = 100
            word_objects = [Word(lexicon=lexicon,wrd=word_sid['word'],suggestionset=suggestionset_map[word_sid['word']]) if word_sid['sid'] >= 0 else Word(lexicon=lexicon,wrd=word_sid['word']) for word_sid in lexicon_words]
            i = 0
            while i < len(word_objects):
                Word.objects.bulk_create(word_objects[i:i+step])
                i += step
                
            logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'lexicon_saved','args':{'user_name':request.user.username,'lexicon_id':lexId,'lexicon_terms':len(lexicon_words)}}))
        else:
            logging.getLogger(INFO_LOGGER).warning(json.dumps({'process':'CREATE LEXICON','event':'lexicon_saving_failed','args':{'user_name':request.user.username,'lexicon_id':lexId},'reason':'No lexicon ID provided.'}))
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE LEXICON','event':'lexicon_saving_failed','args':{'user_name':request.user.username,'lexicon_id':lexId}}),exc_info=True)
        
    return HttpResponseRedirect(URL_PREFIX + '/lm/select?id='+lexId)

@login_required
def selectLexicon(request):
    try:
        template = loader.get_template('lexicon.html')
        lexicon = Lexicon.objects.get(id=request.GET['id'])
        words = Word.objects.filter(lexicon=lexicon)
        words = [a.wrd.encode('utf8') for a in words]
        lexicons = Lexicon.objects.filter(author=request.user)

        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        es_m = ds.build_manager(ES_Manager)
        fields = es_m.get_column_names()
        
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'lexicon_selected','args':{'user_name':request.user.username,'lexicon_id':request.GET['id']},'data':{'lexicon_terms':words}}))
        
        return HttpResponse(template.render({'words':words,'selected':request.GET['id'],'lexicons':lexicons,'STATIC_URL':STATIC_URL,'features':fields},request))
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE LEXICON','event':'lexicon_selection_failed','args':{'user_name':request.user.username,'lexicon_id':request.GET['id']}}),exc_info=True)
        
        return HttpResponseRedirect(URL_PREFIX + '/lm')

@login_required
def query(request):

    try:
        lexicon = Lexicon.objects.get(id=request.POST['lid'])
        suggestionset = SuggestionSet(lexicon=lexicon,method=request.POST['method'])
        suggestionset.save()

        ignored_idxes = model_manager.get_negatives(request.session['model'],request.user.username,lexicon.id)
        
        try:

            model = model_manager.get_model(request.session['model'])
            if model.model.wv.syn0norm is None:
                model.model.init_sims()

        except LookupError:
            
            logging.getLogger(INFO_LOGGER).warning(json.dumps({'process':'CREATE LEXICON','event':'term_suggestion_failed','args':{'user_name':request.user.username,'lexicon_id':request.POST['lid'],'model_id':request.session['model']},'reason':'No lexicon ID provided.'}))
            return HttpResponse('INVALID MODEL')

        suggestionset_id = suggestionset.id
        
        #Add unselected previous suggestions as negative examples.
        if 'negatives' in request.POST and len(request.POST['negatives']) > 2 and 'sid' in request.POST and request.POST['sid'] != -1:
            negatives = [model.vocab[negative.encode('utf8')].index for negative in json.loads(request.POST['negatives']) if negative.encode('utf8') in model.vocab]
            ignored_idxes.extend(negatives)

        positives = [elem.lower().encode('utf8') for elem in request.POST['content'].split('\n') if elem != u'' and elem.lower().encode('utf8') in model.vocab] # or ...AND elem in model.vocab]

        if not positives:
            return HttpResponse('<br><b style="color:red;">No suggestions available for the lexicon. Try adding more terms.</b>')

        suggestions = []

        model_run_obj = ModelRun.objects.get(id=int(request.session['model']))
        tooltip_feature = model_run_obj.fields
        
        # Define selected mapping
        ds = Datasets().activate_dataset(request.session)
        dataset = ds.get_index()
        mapping = ds.get_mapping()

        if request.POST['method'][:12] == 'most_similar':
            for a in getattr(model,request.POST['method'])(positive=positives,topn=40,ignored_idxes = ignored_idxes):
                encoded_a = encode_for_id(a[0])
                
                query = json.dumps({ "size":10, "fields":[tooltip_feature], "query": { "match": {tooltip_feature: a[0]} } })
                response = ES_Manager.plain_scroll(es_url, dataset, mapping, query)
                matched_sentences = []
                for hit in response['hits']['hits']:
                    matched_sentences.append(hit['fields'][tooltip_feature][0].encode('utf-8') if isinstance(hit['fields'][tooltip_feature][0],unicode) else hit['fields'][tooltip_feature][0])
                
                suggestions.append('<div class=\'list_item\' id=\'suggestion_' + encoded_a + '\'>&bull; <a title="' + '\n'.join(matched_sentences).replace('"','') + '" href="javascript:addWord(\''+encoded_a+'\');">'+a[0]+'</a></div>')
        elif request.POST['method'][:17] == 'simple_precluster':
            method = request.POST['method'][18:]

            preclusters = PreclusterMaker(positives,[model.model.syn0norm[model.vocab[positive].index] for positive in positives])()
            
            labels, vectors = zip(*[zip(*cluster) for cluster in preclusters])

            selected_cluster = random.randint(0,len(labels)-1)

            new_positives = labels[selected_cluster]

            label_idxes = [[model.vocab[label].index for label in labels[cluster_idx]] for cluster_idx in range(len(labels))]
            ignored_idxes.extend([label_idxes[cluster_idx][inner_cluster_idx] for cluster_idx in range(len(label_idxes)) if cluster_idx != selected_cluster for inner_cluster_idx in range(len(label_idxes[cluster_idx]))])
            
            for a in getattr(model,method)(positive=new_positives,topn=40,ignored_idxes = ignored_idxes):
                encoded_a = encode_for_id(a[0])
                
                query = json.dumps({ "size":10, "fields":[tooltip_feature], "query": { "match": {model_run_obj.fields: a[0]} } })
                response = ES_Manager.plain_scroll(es_url, dataset, mapping, query)
                matched_sentences = []
                for hit in response['hits']['hits']:
                    matched_sentences.append(hit['fields'][tooltip_feature][0].encode('utf-8') if isinstance(hit['fields'][tooltip_feature][0],unicode) else hit['fields'][tooltip_feature][0])
                
                suggestions.append('<div class=\'list_item\' id=\'suggestion_' + encoded_a + '\'>&bull; <a title="' + '\n'.join(matched_sentences).replace('"','') + '" href="javascript:addWord(\''+encoded_a+'\');">'+a[0]+'</a></div>')

            
        elif request.POST['method'][:10] == 'precluster':
            method = request.POST['method'][11:]

            if len(positives) > 0:
                preclusters = PreclusterMaker(positives,[model.model.syn0norm[model.vocab[positive].index] for positive in positives])()

                labels, vectors = zip(*[zip(*cluster) for cluster in preclusters])
                label_idxes = [[model.vocab[label].index for label in labels[cluster_idx]] for cluster_idx in range(len(labels))]
                suggestions_per_cluster = [zip(*getattr(model,method)(positive=labels[cluster_idx],topn=50,ignored_idxes = ignored_idxes + [label_idxes[i][j] for i in range(len(label_idxes)) for j in range(len(label_idxes[i])) if i != cluster_idx]))[0] for cluster_idx in range(len(labels))]

                suggestions_list = suggestions_per_cluster
                suggestions = RRA_suggestions(suggestions_list,model_run_obj,dataset,mapping,tooltip_feature)
            else:
                suggestions = []
        else:
            #RobustRankAggreg
            _, local_method = request.POST['method'].split()
            local_suggestions = [[similar[0] for similar in getattr(model,local_method)(positive=[positive],topn=50,ignored_idxes=ignored_idxes) if similar[0] not in positives ] for positive in positives]
            suggestions_list = local_suggestions

            suggestions = RRA_suggestions(suggestions_list,model_run_obj,dataset,mapping,tooltip_feature)
        
        suggestions.append('<input type=\'hidden\' id=\'sid\' value=\'' + str(suggestionset_id) + '\'/>') # hidden field to store previous suggestionset's id
        
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'terms_suggested','args':{'user_name':request.user.username,'lexicon_id':request.POST['lid'],'suggestion_method':request.POST['method']}}))
        
        return HttpResponse(['<table><tr><td id=\'suggestion_cell_1\'>'] + suggestions[:20] + ['</td><td id=\'suggestion_cell_2\'>'] + suggestions[20:] + ['</td></tr></table>'])
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).error(json.dumps({'process':'CREATE LEXICON','event':'term_suggestion_failed','args':{'user_name':request.user.username,'lexicon_id':request.POST['lid'],'suggestion_method':request.POST['method']}}),exc_info=True)
        return HttpResponse()


def RRA_suggestions(suggestions_list,modelrun,es_dataset,es_mapping,tooltip_feature):
    ranks = aggregate_ranks(suggestions_list)
    encoded_suggestions = [(name, encode_for_id(name)) for (name, score) in ranks[:40]]
    
    suggestions = []
    for (name,encoded) in encoded_suggestions:
        
        query = json.dumps({ "size":10, "fields":[tooltip_feature], "query": { "match": {modelrun.fields: name} } })
        response = ES_Manager.plain_scroll(es_url, es_dataset, es_mapping, query)
        matched_sentences = []
        for hit in response['hits']['hits']:
            matched_sentences.append(hit['fields'][tooltip_feature][0].encode('utf-8') if isinstance(hit['fields'][tooltip_feature][0],unicode) else hit['fields'][tooltip_feature][0])
    
        suggestions.append('<div class=\'list_item\' id=\'suggestion_' + encoded + '\'>&bull; <a title="' + '\n'.join(matched_sentences).replace('"','') + '" href="javascript:addWord(\'' + encoded + '\');">' + name + '</a></div>')
    return suggestions


def encode_for_id(s):
    # replacing punctuation with corresponding strings to avoid id value conflicts in browser
    for punct in punct_to_name:
        s = s.replace(punct,punct_to_name[punct])
    return s

@login_required
def reset_suggestions(request):
    lexicon_id = request.POST['lid']
    
    try:
        model_manager.reset_negatives(request.session['model'],request.user.username,int(lexicon_id))
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'suggestions_reset','args':{'user_name':request.user.username,'lexicon_id':lexicon_id}}))
    except Exception as e:
        logging.getLogger(INFO_LOGGER).info(json.dumps({'process':'CREATE LEXICON','event':'suggestions_reset','args':{'user_name':request.user.username,'lexicon_id':lexicon_id}}),exc_info=True)
    return HttpResponseRedirect(URL_PREFIX + '/lm/select?id='+lexicon_id)
