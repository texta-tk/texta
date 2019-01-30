from __future__ import absolute_import
import json
import pprint

from django.http import HttpResponse, HttpResponseRedirect, StreamingHttpResponse
from django.template import loader, Context
from django.contrib.auth.decorators import login_required
import requests

from searcher.views import Search
from utils.datasets import Datasets
from utils.es_manager import ES_Manager

from texta.settings import STATIC_URL, URL_PREFIX, es_url

from task_manager.models import Task
from permission_admin.models import Dataset
from conceptualiser.models import Term, TermConcept, Concept
from grammar_builder.models import GrammarComponent, GrammarPageMapping, Grammar
from . import multilayer_matcher as matcher

from .elastic_grammar_query import ElasticGrammarQuery

from collections import defaultdict

import csv

import sys, os

try:
    from io import BytesIO
except:
    from io import StringIO

ES_SCROLL_BATCH = 100

@login_required
def index(request):
    # Define selected mapping
    ds = Datasets().activate_dataset(request.session)
    dataset = ds.get_index()
    mapping = ds.get_mapping()

    es_m = ds.build_manager(ES_Manager)

    fields = get_fields(es_m)

    searches = [{'id':search.pk,'desc':search.description} for search in
                Search.objects.filter(author=request.user, dataset__index=dataset, dataset__mapping=mapping)]

    datasets = Datasets().get_allowed_datasets(request.user)
    language_models = Task.objects.filter(task_type='train_model').filter(status=Task.STATUS_COMPLETED).order_by('-pk')

    template = loader.get_template('grammar_builder.html')
    return HttpResponse(template.render({'STATIC_URL':STATIC_URL,
                                         'searches':searches,
                                         'features':fields,
                                         'language_models': language_models,
                                         'allowed_datasets': datasets},request))

def get_fields(es_m):
    """ Create field list from fields in the Elasticsearch mapping
    """
    fields = []
    mapped_fields = es_m.get_mapped_fields()

    for data in mapped_fields:
        path = data['path']
        fields.append(path)

    # Sort fields by label
    fields.sort()

    return fields

@login_required
def save_component(request):
    name = request.POST['name']
    type_ = request.POST['type']
    content = request.POST['content']
    sub_components = json.loads(request.POST['sub_components'])
    layer = request.POST['layer'] if type_ in {'exact':None, 'regex': None} else None
    join_by = request.POST['join_by'] if type_ == 'exact' else None
    new_grammar = GrammarComponent(name=name, type=type_, content=content, layer=layer, join_by=join_by, author=request.user)
    new_grammar.save()
    if sub_components:
        sub_component_objs = GrammarComponent.objects.filter(id__in=sub_components)
        new_grammar.sub_components.add(*sub_component_objs)
    return HttpResponse(json.dumps({'id':new_grammar.id}))

@login_required
def get_components(request):
    components = GrammarComponent.objects.filter(author=request.user)
    return HttpResponse(json.dumps([{'name':component.name, 'id':component.id} for component in components]))

@login_required
def get_component_JSON(request):
    component_id = request.GET['id']
    metaquery_dict = generate_metaquery_dict(component_id, request.user)
    return HttpResponse(json.dumps(metaquery_dict))

def expand_concept(concept_name, user):
    author_concepts = Concept.object.filter(author=user)

    if author_concepts:
        concept = author_concepts.filter(descriptive_term__term=concept_name)
        if concept:
            return [term_concept.term.term for term_concept in TermConcept.object.filter(concept=concept)]
        else:
            return ["@"+concept_name]
    else:
        return ["@"+concept_name]

    concept_term = Term.objects.filter(author=user).filter(term__term=concept_name)


def generate_metaquery_dict(component_idx, user, component={}):
    #print(component_idx)
    """Generates a hierarchical grammar in the form of dictionary which can be fed to ElasticGrammarQuery.
    E.g {'operation':'intersection','name':'my_intersect1','components':[{'operation':'exact','layer':'lemmas','name':'dog_lemmas','terms':['dog','puppy','doggie'],'join_by':'intersect'}]}

    """
    final_dict_component = component
    #print(GrammarComponent.objects.get(pk=component_idx))
    components = [(GrammarComponent.objects.get(pk=component_idx),final_dict_component)]
    while len(components):
        current_model_component, current_dict_component  = components.pop()

        current_name = current_model_component.name
        current_type = current_model_component.type

        current_dict_component['name'] = current_name
        current_dict_component['operation'] = current_type

        if current_type in set(['exact','regex']):
            current_dict_component['layer'] = current_model_component.layer
            if current_type == 'exact':
                current_dict_component['join_by'] = current_model_component.join_by
                initial_terms = json.loads(current_model_component.content)
                final_terms = [[initial_term] if not initial_term.startswith("@") else expand_concept(initial_term[1:], user) for initial_term in initial_terms]
                current_dict_component['terms'] = [final_term for terms_collection in final_terms for final_term in final_terms]
            else:
                current_dict_component['expression'] = current_model_component.content
        else:
            sub_components = current_model_component.sub_components.all()
            current_dict_component['components'] = [{} for i in range(len(sub_components))]
            components.extend([(model_component, current_dict_component['components'][component_idx])
                               for component_idx, model_component in enumerate(sub_components)])


    return final_dict_component


def generate_instructions(metaquery_dict):

    components = [{'raw':metaquery_dict, }]

    operation_to_class = {'gap': matcher.Gap, 'concat': matcher.Concatenation, 'intersect': matcher.Intersection, 'union': matcher.Union}

    def generation_helper(component_dict):
        if 'layer' in component_dict:
            if component_dict['operation'] == 'exact':
                return matcher.Exact(component_dict['terms'],component_dict['layer'],component_dict['sensitive'])
            elif component_dict['operation'] == 'regex':
                return matcher.Regex(component_dict['expression'],component_dict['layer'],component_dict['sensitive'])
        else:
            sub_instructions = [generation_helper(sub_component) for sub_component in component_dict['components']]
            if component_dict['operation'] == 'gap':
                return matcher.Gap(sub_instructions, slop=component_dict['slop'], match_first=component_dict['matchFirst'])

            return operation_to_class[component_dict['operation']](sub_instructions)

    return generation_helper(metaquery_dict)

@login_required
def get_table(request):
    polarity = request.GET['polarity']

    if request.GET['is_test'] == 'true':
        inclusive_test_grammar = json.loads(request.GET['inclusive_test_grammar'])
        #exclusive_test_grammar = json.loads(request.GET['exclusive_test_grammar'])

        layers = ['id'] + sorted(extract_layers(inclusive_test_grammar))
    else:
        inclusive_id = int(request.GET['inclusive_grammar_id'])
        exclusive_id = int(request.GET['exclusive_grammar_id'])

        inclusive_metaquery = generate_metaquery_dict(inclusive_id, request.user, component={})
        exclusive_metaquery = generate_metaquery_dict(exclusive_id, request.user, component={})
        layers = ['id'] + sorted(extract_layers(inclusive_metaquery) | extract_layers(exclusive_metaquery))

    template = loader.get_template('grammar_builder_table.html')
    return HttpResponse(template.render({'features':layers, 'polarity':polarity},request))

@login_required
def get_grammar_listing(request):
    ds = Datasets().activate_dataset(request.session)
    dataset = ds.get_index()
    mapping = ds.get_mapping()

    grammars = Grammar.objects.filter(author=request.user, dataset__index=dataset, dataset__mapping=mapping).order_by('-last_modified')
    grammar_json = json.dumps([{'id':grammar.id, 'name':grammar.name, 'last_modified':grammar.last_modified.strftime("%d/%m/%y %H:%M:%S")} for grammar in grammars])

    return HttpResponse(grammar_json)

@login_required
def save_grammar(request):
    grammar_dict = json.loads(request.POST['json'])

    grammar_id = grammar_dict[0]['id']

    if grammar_id == 'new':
        name = grammar_dict[0]['text']

        ds = Datasets().activate_dataset(request.session)
        dataset = ds.get_index()
        mapping = ds.get_mapping()

        grammar = Grammar(name=name, json='', author=request.user, dataset=Dataset.objects.filter(index=dataset, mapping=mapping)[0])
        grammar.save()

        grammar_dict[0]['id'] = grammar.id
    else:
        grammar = Grammar.objects.get(id=grammar_id)

    grammar.json = json.dumps(grammar_dict)
    grammar.save()

    return HttpResponse(json.dumps({'id':grammar.id}))

@login_required
def get_grammar(request):
    grammar_id = request.GET['id']
    grammar_json = Grammar.objects.get(id=grammar_id).json

    return HttpResponse(grammar_json)

@login_required
def delete_grammar(request):
    grammar_id = request.GET['id']
    Grammar.objects.get(id=grammar_id).delete()

    return HttpResponse()

def extract_layers(metaquery_dict):
    layers = set()

    nodes = [metaquery_dict]
    while len(nodes) > 0:
        current_node = nodes.pop()
        if 'layer' in current_node:
            layers.add(current_node['layer'])
        if 'components' in current_node:
            nodes.extend(current_node['components'])

    return layers

"""
@login_required
def get_table(request):
    template = loader.get_template('grammar_builder/grammar_builder_table.html')
    return HttpResponse(template.render({'feature':request.POST['feature']},request))
"""

@login_required
def export_matched_data(request):
    search_id = request.GET['search_id']

    inclusive_metaquery = json.loads(request.GET['inclusive_grammar'])

    ds = Datasets().activate_dataset(request.session)

    component_query = ElasticGrammarQuery(inclusive_metaquery, None).generate()

    es_m = ds.build_manager(ES_Manager)

    if search_id == '-1': # Full search
        es_m.combined_query = component_query
    else:
        saved_query = json.loads(Search.objects.get(pk=search_id).query)
        es_m.load_combined_query(saved_query)
        es_m.merge_combined_query_with_query_dict(component_query)

    inclusive_instructions = generate_instructions(inclusive_metaquery)

    response = StreamingHttpResponse(get_all_matched_rows(es_m.combined_query['main'], request, inclusive_instructions), content_type='text/csv')

    response['Content-Disposition'] = 'attachment; filename="%s"' % ('extracted.csv')

    return response

def get_all_matched_rows(query, request, inclusive_instructions):
    buffer_ = StringIO()
    writer = csv.writer(buffer_)

    ds = Datasets().activate_dataset(request.session)
    es_m = ds.build_manager(ES_Manager)

    features = sorted([field['path'] for field in es_m.get_mapped_fields()])

    query['size'] = ES_SCROLL_BATCH

    writer.writerow(features)

    ds.get_index()
    ds.get_mapping()
    es_url

    request_url = os.path.join(es_url, ds.get_index(), ds.get_mapping(), '_search?scroll=1m')
    response = requests.get(request_url, data=json.dumps(query)).json()

    scroll_id = response['_scroll_id']
    hits = response['hits']['hits']

    scroll_payload = json.dumps({'scroll':'1m', 'scroll_id':scroll_id})
    while hits:
        for hit in hits:
            feature_dict = {feature_name:hit['_source'][feature_name] for feature_name in hit['_source']}

            feature_dict = {}

            row = []
            for feature_name in features:
                feature_path = feature_name.split('.')
                parent_source = hit['_source']
                for path_component in feature_path:
                    if path_component in parent_source:
                        parent_source = parent_source[path_component]
                    else:
                        parent_source = ""
                        break

                content = parent_source
                row.append(content)
                feature_dict[feature_name] = content

            layer_dict = matcher.LayerDict(feature_dict)
            if inclusive_instructions.match(layer_dict):
                writer.writerow([element.encode('utf-8') if isinstance(element,unicode) else element for element in row])

        buffer_.seek(0)
        data = buffer_.read()
        buffer_.seek(0)
        buffer_.truncate()
        yield data

        response = requests.get(os.path.join(es_url,'_search','scroll'), data=scroll_payload).json()
        hits = response['hits']['hits']
        scroll_id = response['_scroll_id']

@login_required
def get_table_data(request):
    query_data = {}

    query_data['search_id'] = request.GET['search_id']
    query_data['polarity'] = request.GET['polarity']
    query_data['requested_page'] = int(request.GET['iDisplayStart'])/int(request.GET['iDisplayLength'])+1
    query_data['page_length'] = int(request.GET['iDisplayLength'])

    if request.GET['is_test'] == 'true':
        query_data['inclusive_metaquery'] = json.loads(request.GET['inclusive_test_grammar'])

        query_data['inclusive_grammar_id'] = -1
        query_data['exclusive_grammar_id'] = -1

        query_data['features'] = sorted(extract_layers(query_data['inclusive_metaquery']))

    else:
        query_data['inclusive_grammar_id'] = request.GET['inclusive_grammar_id']
        query_data['exclusive_grammar_id'] = request.GET['exclusive_grammar_id']

        query_data['inclusive_metaquery'] = generate_metaquery_dict(int(query_data['inclusive_grammar_id']), request.user, component={})
        query_data['exclusive_metaquery'] = generate_metaquery_dict(int(query_data['exclusive_grammar_id']), request.user, component={})

        query_data['features'] = sorted(extract_layers(query_data['inclusive_metaquery']) | extract_layers(query_data['exclusive_metaquery']))


    GrammarPageMapping.objects.filter(search_id=query_data['search_id'],
                                    inclusive_grammar=query_data['inclusive_grammar_id'],
                                    exclusive_grammar=query_data['exclusive_grammar_id'],
                                    polarity=query_data['polarity'], author=request.user).delete()


    ds = Datasets().activate_dataset(request.session)

    query_data['dataset'] = ds.get_index()
    query_data['mapping'] = ds.get_mapping()

    component_query = ElasticGrammarQuery(query_data['inclusive_metaquery'], None).generate()

    es_m = ds.build_manager(ES_Manager)
    if query_data['search_id'] != '-1':
        saved_query = json.loads(Search.objects.get(pk=query_data['search_id']).query)
        es_m.load_combined_query(saved_query)

        if query_data['polarity'] == 'positive':
            es_m.merge_combined_query_with_query_dict(component_query)
    else:
        #es_m.combined_query = {"main": {"query": {"bool": {"should": [{"match_all":{}}], "must": [], "must_not": []}}},
                                #"facts": {"include": [], 'total_include': 0,
                                     #"exclude": [], 'total_exclude': 0}}
        es_m.combined_query = {"main": {"query":{"match_all":{}}}}
        if query_data['polarity'] == 'positive':
            es_m.combined_query = component_query

    # Add paging data to the query
    #es_m.set_query_parameter('from', request.session['grammar_'+polarity+'_cursor'])
    es_m.set_query_parameter('size', request.GET['iDisplayLength'])
    es_m.set_query_parameter('_source', query_data['features'])

    query_data['inclusive_instructions'] = generate_instructions(query_data['inclusive_metaquery'])
    query_data['exclusive_instructions'] = {} #generate_instructions(query_data['exclusive_metaquery'])

    data = scroll_data(es_m.combined_query['main'], request, query_data)
    data['sEcho'] = request.GET['sEcho']

    return HttpResponse(json.dumps(data,ensure_ascii=False))


def scroll_data(query,request, query_data):
    out = {'aaData':[],'iTotalRecords':0,'iTotalDisplayRecords':0}

    positive_polarity = query_data['polarity'] == 'positive'

    rows = out['aaData']
    target_row_no = query_data['page_length']

    grammar_page_mapping = GrammarPageMapping.objects.filter(search_id=query_data['search_id'],
                                                             inclusive_grammar=query_data['inclusive_grammar_id'],
                                                            exclusive_grammar=query_data['exclusive_grammar_id'],
                                                            page=query_data['requested_page'], polarity=query_data['polarity'],
                                                            author=request.user)

    if grammar_page_mapping:
        es_from = grammar_page_mapping[0].elastic_start
    else:
        ordered_pages = GrammarPageMapping.objects.filter(search_id=query_data['search_id'],
                                                          inclusive_grammar=query_data['inclusive_grammar_id'],
                                                            exclusive_grammar=query_data['exclusive_grammar_id'],
                                                            polarity=query_data['polarity'], author=request.user).order_by('-page')
        if ordered_pages:
            max_stored_page, es_from = ordered_pages[0].page, ordered_pages[0].elastic_end
        else:
            max_stored_page, es_from = 0, 0

        es_from = get_es_from(max_stored_page, es_from, request, query, query_data)

    page_data = get_next_page_data(query, es_from, 0, query_data, request)
    rows.extend(page_data['rows'])

    out['iTotalRecords'] = page_data['total']
    out['iTotalDisplayRecords'] = page_data['total']
    return out

def get_es_from(max_stored_page, es_from, request, query, query_data):
    current_page = max_stored_page
    requested_page = query_data['requested_page']
    es_from = es_from
    last_end = es_from

    while current_page < requested_page and es_from != None:
        page_data = get_next_page_data(query, last_end, current_page, query_data, request)
        es_from = page_data['from']
        last_end = page_data['end']
        current_page = page_data['page']

    return es_from


def get_next_page_data(query, es_from, last_page, query_data, request):
    start_from = None
    end = None
    rows = []
    page_length = query_data['page_length']

    if es_from == None:
        return {'rows':rows,'from':start_from,'page':last_page,'end':None, 'total':None}

    dataset = query_data['dataset']
    mapping = query_data['mapping']
    polarity = query_data['polarity']

    inclusive_instructions = query_data['inclusive_instructions']
    exclusive_instructions = query_data['exclusive_instructions']

    query['from'] = es_from
    response = ES_Manager.plain_search(es_url, dataset, mapping, query)

    try:
        hit = response['hits']['hits'][0]
        feature_dict = {feature_name:hit['_source'][feature_name][0] for feature_name in hit['_source']}
        sorted_feature_names = sorted(feature_dict)
        feature_to_idx_map = {feature: (feature_idx+1) for feature_idx, feature in enumerate(sorted_feature_names)}
    except:
        pass

    hit_idx = page_length-1

    while len(rows) < page_length and 'hits' in response and 'hits' in response['hits'] and response['hits']['hits'] and hit_idx+1 == page_length:
        for hit_idx, hit in enumerate(response['hits']['hits']):
            if len(rows) >= page_length:
                break

            feature_dict = {}

            for field_name in hit['_source']:
                field_value = hit['_source'][field_name]
                if isinstance(field_value, dict):
                    for subfield_name, subfield_value in field_value.items():
                        combined_field_name = '{0}.{1}'.format(field_name, subfield_name)
                        feature_dict[combined_field_name] = subfield_value
                else:
                    feature_dict[field_name] = field_value

            sorted_feature_names = sorted(feature_dict)

            feature_to_idx_map = defaultdict(list)
            for feature_idx, feature in enumerate(sorted_feature_names):
                feature_to_idx_map[feature.split('.')[0]].append(feature_idx+1)

            row = [hit['_id']]
            row.extend([feature_dict[feature_name] for feature_name in sorted_feature_names])
            layer_dict = matcher.LayerDict(feature_dict)

            inclusive_matches = inclusive_instructions.match(layer_dict)

            if (polarity == 'positive') == bool(inclusive_matches): # add row if polarity is positive and we have a match or negative and dont
                if len(rows) == 0:
                    start_from = query['from'] + hit_idx
                end = query['from'] + hit_idx

                if inclusive_matches:
                    row = highlight(row, feature_to_idx_map, inclusive_matches)

                rows.append(row)

        query['from'] = query['from'] + hit_idx + 1

        if len(rows) >= page_length:
            break
        response = ES_Manager.plain_search(es_url, dataset, mapping,query)
    if end:
        GrammarPageMapping(search_id=query_data['search_id'], inclusive_grammar=query_data['inclusive_grammar_id'],
                        exclusive_grammar=query_data['exclusive_grammar_id'], page=query_data['requested_page'], polarity=query_data['polarity'],
                        elastic_start=start_from, elastic_end=end+1, author=request.user).save()

    return {'rows':rows,'from':start_from,'page':last_page+1,'end':(end+(0 if last_page == 0 else 1)) if end else end, 'total':response['hits']['total']}

def highlight(row, feature_to_idx_map, inclusive_matches):
    colours = defaultdict(lambda: defaultdict(list))
    titles = defaultdict(lambda: defaultdict(list))
    for match_idx, match in enumerate(inclusive_matches):
        for meta_token_idx, token_idx in enumerate(match.token_idxs):
            feature = match.features[meta_token_idx]
            colours[feature][token_idx].append('#FFFF00')
            titles[feature][token_idx].append(match_idx)

    for feature in colours:
        for feature_idx in feature_to_idx_map[feature]:
            feature_tokens = row[feature_idx].split()
            for token_idx in colours[feature]:
                new_token = annotate_token(feature_tokens[token_idx], titles[feature][token_idx], colours[feature][token_idx])
                feature_tokens[token_idx] = new_token

            row[feature_idx] = ' '.join(feature_tokens)

    return row

def annotate_token(token, titles, colours):
    output = ['<span title="']
    output.append(' '.join(str(title) for title in titles))
    output.append('" style="background-color: ')
    output.append(colours[0])
    output.append(';">')
    output.append(token)
    output.append('</span>')
    return ''.join(output)
