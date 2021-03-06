# -*- coding: utf8 -*-
import random
import json
import logging

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.template import loader
from django.http import QueryDict
import requests


from .models import Lexicon, Word, SuggestionSet
from task_manager.models import Task
from utils.robust_rank_aggregation import aggregate_ranks
from utils.model_manager import get_model_manager
from utils.precluster import PreclusterMaker
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import URL_PREFIX, STATIC_URL, INFO_LOGGER, ERROR_LOGGER
from texta.settings import es_url, es_links
from task_manager.tasks.task_types import TaskTypes



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
    datasets = Datasets().get_allowed_datasets(request.user)
    language_models =Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL.value).filter(status__iexact=Task.STATUS_COMPLETED).order_by('-pk')

    template = loader.get_template('lm.html')
    lexicons = Lexicon.objects.all().filter(author=request.user)
    return HttpResponse(template.render({'lexicons': lexicons, 'STATIC_URL': STATIC_URL, 'language_models': language_models, 'allowed_datasets': datasets}, request))


@login_required
def newLexicon(request):
    """Creates a new lexicon, either through lm, or via creating one externally (for example a cluster form cluster search)

    Arguments:
        request {request} -- POST request containing the lexicon name and (if external) lexicon keywords

    Returns:
        HttpResponseRedirect -- If created in lm, then redirects to new lexicon, else doesn't return anything
    """
    lexiconName = request.POST['lexiconname']
    if(lexiconName == ''):
        return returnAjaxResult('error', 'Lexicon name can\'t be empty')

    if 'lexiconkeywords' in request.POST:
        lexiconKeywords = request.POST['lexiconkeywords']
    else:
        lexiconKeywords = None

    try:
        Lexicon(name=lexiconName,description='na',author=request.user).save()
    except Exception as e:
        log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_creation_failed', 'arguments': {'user_name': request.user.username, 'lexicon_name': lexiconName}}
        logging.getLogger(ERROR_LOGGER).error("Lexicon creation failed", extra=log_dict, exc_info=True)

    log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_created', 'arguments': {'user_name': request.user.username, 'lexicon_name': lexiconName}}
    logging.getLogger(INFO_LOGGER).info("Lexicon created", extra=log_dict)

    if 'ajax_lexicon_miner' in request.POST:
        return returnAjaxResult('success', URL_PREFIX + '/lexicon_miner/select?id='+str(Lexicon.objects.filter(name=lexiconName).last().id))
    
    if lexiconKeywords:
        request.POST._mutable = True
        request.POST = QueryDict('', mutable=True)
        request.POST.update({'id': str(Lexicon.objects.filter(name=lexiconName).last().id), 'lexicon': [{"word": word, "sid": -1} for word in lexiconKeywords.split(' ')]})
        request.POST._mutable = False
        saveLexicon(request, local_request=True)

        return HttpResponse()
    else:
        # last to get the latest entry just in case there is a duplicate
        return HttpResponseRedirect(URL_PREFIX + '/lexicon_miner/select?id='+str(Lexicon.objects.filter(name=lexiconName).last().id))

def returnAjaxResult(result, message):
    response_data = {}
    response_data['result'] = result
    response_data['message'] = message
    return JsonResponse(response_data)

@login_required
def deleteLexicon(request):
    try:
        lexicon = Lexicon.objects.get(id=request.GET['id'])
        # if the user tries to delete a lexicon with no model it throws an error
        if('model' in request.session):
            model_manager.remove_negatives(request.session['model']['pk'],request.user.username,lexicon.id)
        Word.objects.filter(lexicon=lexicon).delete()
        lexicon.delete()

        log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_deleted', 'arguments': {'user_name': request.user.username, 'lexicon_id': request.GET['id']}}
        logging.getLogger(INFO_LOGGER).info("Lexicon deleted", extra=log_dict)

    except Exception as e:
        log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_deletion_failed', 'arguments': {'user_name': request.user.username, 'lexicon_id': request.GET['id']}}
        logging.getLogger(ERROR_LOGGER).error("Lexicon deletion failed", extra=log_dict, exc_info=True)

    return HttpResponseRedirect(URL_PREFIX + '/lexicon_miner')


@login_required
def saveLexicon(request, local_request=False):
    """Save a lexicon, either through lm or (if external) through the newLexicon function

    Arguments:
        request {requst} -- POST request containing the lexicon id and values, ex:
    <QueryDict: {'id': ['60'], 'lexicon': ['[{"word":"pani","sid":-1},{"word":"panid","sid":387},{"word":"paneb","sid":387}]']}>

    Keyword Arguments:
        local_request {bool} -- True if the lexicon is created externally, then the saveLexicon call and request is created locally  (default: {True})

    Returns:
        HttpResponseRedirect -- If created through lm, redirect to the selected id, else don't redirect
    """

    lexId = request.POST['id']

    try:
        if lexId:
            lexicon = Lexicon.objects.get(id=lexId)
            Word.objects.filter(lexicon=lexicon).delete()

            try:
                model_manager.save_negatives(request.session['model']['pk'],request.user.username,lexicon.id)
            except KeyError:
                log_dict = {'task': 'SAVE LEXICON', 'event': 'negatives_saving_failed', 'arguments': {'user_name': request.user.username, 'lexicon_id': lexId}, 'reason': 'no negatives to save'}
                logging.getLogger(INFO_LOGGER).warning("Saving negatices failed", extra=log_dict)


            # Fix problems with '' and ""
            if local_request:
                lexicon_words = uniq(json.loads(json.dumps(request.POST['lexicon'])))
            else:
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
            log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_saved', 'arguments': {'user_name': request.user.username, 'lexicon_id': lexId, 'lexicon_terms': len(lexicon_words)}}
            logging.getLogger(INFO_LOGGER).info("Lexicon saved", extra=log_dict)

        else:
            log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_saving_failed', 'arguments': {'user_name': request.user.username, 'lexicon_id': lexId}, 'reason': 'No lexicon ID provided.'}
            logging.getLogger(INFO_LOGGER).warning("Lexicon saving failed", extra=log_dict)

    except Exception as e:
        log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_saving_failed', 'arguments': {'user_name': request.user.username, 'lexicon_id': lexId}}
        logging.getLogger(ERROR_LOGGER).error("Lexicon saving failed", extra=log_dict, exc_info=True)

    if not local_request:
        return HttpResponseRedirect(URL_PREFIX + '/lexicon_miner/select?id='+lexId)



@login_required
def selectLexicon(request):
    try:
        template = loader.get_template('lexicon.html')
        lexicon = Lexicon.objects.get(id=request.GET['id'])
        words = Word.objects.filter(lexicon=lexicon)
        words = [a.wrd for a in words]
        lexicons = Lexicon.objects.filter(author=request.user)

        datasets = Datasets().get_allowed_datasets(request.user)
        language_models =Task.objects.filter(task_type=TaskTypes.TRAIN_MODEL.value).filter(status=Task.STATUS_COMPLETED).order_by('-pk')

        # Define selected mapping
        ds = Datasets().activate_datasets(request.session)
        es_m = ds.build_manager(ES_Manager)
        fields = es_m.get_column_names()

        log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_selected', 'arguments': {'user_name': request.user.username, 'lexicon_id': request.GET['id']}, 'data': {'lexicon_terms': words}}
        logging.getLogger(INFO_LOGGER).info("Lexicon selected", extra=log_dict)
        
        return HttpResponse(template.render({'words':words,'selected':request.GET['id'], 'selected_name':lexicon,'lexicons':lexicons,'STATIC_URL':STATIC_URL,'features':fields, 'language_models': language_models, 'allowed_datasets': datasets}, request))
    
    except Exception as e:
        log_dict = {'task': 'CREATE LEXICON', 'event': 'lexicon_selection_failed', 'arguments': {'user_name': request.user.username, 'lexicon_id': request.GET['id']}}
        logging.getLogger(ERROR_LOGGER).error("Lexicon selection failed", extra=log_dict, exc_info=True)
        return HttpResponseRedirect(URL_PREFIX + '/lexicon_miner')


def get_example_texts(request, field, value):
    ds = Datasets().activate_datasets(request.session)
    es_m = ds.build_manager(ES_Manager)
    query = { "size":10, "highlight": {"fields": {field: {}}}, "query": {"match": {field: value}}}
    response = es_m.perform_query(query)
    matched_sentences = []
    for hit in response['hits']['hits']:
        for match in hit['highlight'].values():
            matched_sentences.append(match[0])
    return matched_sentences


def prepare_suggestion(request, suggestion, tooltip_feature):
    matched_sentences = get_example_texts(request, tooltip_feature, suggestion)
    matched_sentences = '\n'.join(matched_sentences).replace('"','')
    suggestion = suggestion.replace('_', ' ')
    suggestion = '<div class=\'list_item\' id=\'suggestion_{0}\'>&bull; <a role="button" title="{1}" onclick="javascript:addWord(this,\'{0}\');">{0}</a></div>'.format(suggestion, matched_sentences)
    return suggestion


@login_required
def query(request):
    try:
        lexicon = Lexicon.objects.get(id=request.POST['lid'])
        suggestionset = SuggestionSet(lexicon=lexicon,method=request.POST['method'])
        suggestionset.save()

        ignored_idxes = model_manager.get_negatives(request.session['model']['unique_id'],request.user.username,lexicon.id)
        model = model_manager.get_model(request.session['model']['unique_id'])
        if model.model.wv.syn0norm is None:
            model.model.init_sims()

        suggestionset_id = suggestionset.id

        #Add unselected previous suggestions as negative examples.
        if 'negatives' in request.POST and len(request.POST['negatives']) > 2 and 'sid' in request.POST and request.POST['sid'] != -1:
            negatives = [model.vocab[negative.replace(' ', '_')].index for negative in json.loads(request.POST['negatives']) if negative.replace(' ', '_') in model.vocab]
            ignored_idxes.extend(negatives)

        positives = [elem.lower().replace(' ', '_') for elem in request.POST['content'].split('\n') if elem.lower() in model.vocab] # or ...AND elem in model.vocab]

        if not positives:
            return HttpResponse('<br><b style="color:red;">No suggestions available for the lexicon. Try adding more terms.</b>')

        suggestions = []
        
        model_run_obj = Task.objects.get(id=int(request.session['model']['pk']))
        tooltip_feature = json.loads(model_run_obj.parameters)['field']

        if request.POST['method'][:12] == 'most_similar':
            for a in getattr(model,request.POST['method'])(positive=positives, topn=40, ignored_idxes=ignored_idxes):
                suggestion = prepare_suggestion(request, a[0], tooltip_feature)
                suggestions.append(suggestion)

        elif request.POST['method'][:17] == 'simple_precluster':
            method = request.POST['method'][18:]
            preclusters = PreclusterMaker(positives,[model.model.wv.syn0norm[model.vocab[positive].index] for positive in positives])()
            labels, vectors = zip(*[zip(*cluster) for cluster in preclusters])
            selected_cluster = random.randint(0,len(labels)-1)
            new_positives = labels[selected_cluster]
            label_idxes = [[model.vocab[label].index for label in labels[cluster_idx]] for cluster_idx in range(len(labels))]
            ignored_idxes.extend([label_idxes[cluster_idx][inner_cluster_idx] for cluster_idx in range(len(label_idxes)) if cluster_idx != selected_cluster for inner_cluster_idx in range(len(label_idxes[cluster_idx]))])
            for a in getattr(model,method)(positive=new_positives,topn=40,ignored_idxes = ignored_idxes):
                suggestion = prepare_suggestion(request, a[0], tooltip_feature)
                suggestions.append(suggestion)
                
        elif request.POST['method'][:10] == 'precluster':
            method = request.POST['method'][11:]
            if len(positives) > 0:
                preclusters = PreclusterMaker(positives,[model.model.wv.syn0norm[model.vocab[positive].index] for positive in positives])()
                labels, vectors = zip(*[zip(*cluster) for cluster in preclusters])
                label_idxes = [[model.vocab[label].index for label in labels[cluster_idx]] for cluster_idx in range(len(labels))]
                suggestions_per_cluster = [list(zip(*getattr(model,method)(positive=labels[cluster_idx],topn=50,ignored_idxes = ignored_idxes + [label_idxes[i][j] for i in range(len(label_idxes)) for j in range(len(label_idxes[i])) if i != cluster_idx])))[0] for cluster_idx in range(len(labels))]
                suggestions_list = suggestions_per_cluster
                suggestions = RRA_suggestions(suggestions_list, tooltip_feature, request)
            else:
                suggestions = []
        else:
            #RobustRankAggreg
            _, local_method = request.POST['method'].split()
            local_suggestions = [[similar[0] for similar in getattr(model,local_method)(positive=[positive],topn=50,ignored_idxes=ignored_idxes) if similar[0] not in positives ] for positive in positives]
            suggestions_list = local_suggestions
            suggestions = RRA_suggestions(suggestions_list, tooltip_feature, request)

        suggestions.append('<input type=\'hidden\' id=\'sid\' value=\'' + str(suggestionset_id) + '\'/>') # hidden field to store previous suggestionset's id

        log_dict = {'task': 'TERM SUGGESTION', 'event': 'terms_suggested', 'arguments': {'user_name': request.user.username, 'lexicon_id': request.POST['lid'], 'suggestion_method': request.POST['method']}}
        logging.getLogger(INFO_LOGGER).info("Suggested terms", extra=log_dict)

        return HttpResponse(['<table class="width-max"><tr class="flex-content-space-around"><td id=\'suggestion_cell_1\'>'] + suggestions[:20] + ['</td><td id=\'suggestion_cell_2\'>'] + suggestions[20:] + ['</td></tr></table>'])

    except Exception as e:
        log_dict = {'task': 'TERM SUGGESTION', 'event': 'term_suggestion_failed', 'arguments': {'user_name': request.user.username, 'lexicon_id': request.POST['lid'], 'suggestion_method': request.POST['method']}}
        logging.getLogger(ERROR_LOGGER).error("Term suggestion failed", extra=log_dict, exc_info=True)
        return HttpResponse()


def RRA_suggestions(suggestions_list, tooltip_feature, request):
    ranks = aggregate_ranks(suggestions_list)
    encoded_suggestions = [name for (name, score) in ranks[:40]]
    suggestions = []
    for name in encoded_suggestions:
        suggestion = prepare_suggestion(request, name, tooltip_feature)
        suggestions.append(suggestion)
    return suggestions


@login_required
def reset_suggestions(request):
    lexicon_id = request.POST['lid']
    try:
        model_manager.reset_negatives(request.session['model']['pk'],request.user.username,int(lexicon_id))
        log_dict = {'task': 'CREATE LEXICON', 'event': 'suggestions_reset', 'arguments': {'user_name': request.user.username, 'lexicon_id': lexicon_id}}
        logging.getLogger(INFO_LOGGER).info("Reset suggestions", extra=log_dict)

    except Exception as e:
        log_dict = {'task': 'CREATE LEXICON', 'event': 'suggestions_reset', 'arguments': {'user_name': request.user.username, 'lexicon_id': lexicon_id}}
        logging.getLogger(INFO_LOGGER).info("Reset suggestions", extra=log_dict, exc_info=True)

    return HttpResponseRedirect(URL_PREFIX + '/lexicon_miner/select?id='+lexicon_id)
