from collections import OrderedDict, defaultdict
from collections import Counter
from utils.highlighter import Highlighter, ColorPicker
from searcher.view_functions.general.searcher_utils import additional_option_cut_text
from searcher.view_functions.build_search.translit_highlighting import hl_transliterately
import time
import json

def execute_search(es_m, es_params):
    start_time = time.time()
    out = {'column_names': [],'aaData': [],'iTotalRecords': 0,'iTotalDisplayRecords': 0,'lag': 0}
    # DEFINING THE EXAMPLE SIZE
    es_m.set_query_parameter('from', es_params['examples_start'])
    es_m.set_query_parameter('size', es_params['num_examples'])

    # HIGHLIGHTING THE MATCHING FIELDS
    hl_config = _derive_hl_config(es_params)
    es_m.set_query_parameter('highlight', hl_config)
    response = es_m.search()

    out['iTotalRecords'] = response['hits']['total']
    out['iTotalDisplayRecords'] = response['hits']['total'] # number of docs

    if int(out['iTotalDisplayRecords']) > 10000: # Allow less pages if over page limit
        out['iTotalDisplayRecords'] = '10000'
    out['column_names'] = es_m.get_column_names() # get columns names from ES mapping

    for hit in response['hits']['hits']:
        hit_id = str(hit['_id'])
        row = OrderedDict([(x, '') for x in out['column_names']]) # OrderedDict to remember column names with their content

        inner_hits = hit['inner_hits'] if 'inner_hits' in hit else {}
        name_to_inner_hits = _derive_name_to_inner_hits(inner_hits)

        # Fill the row content respecting the order of the columns
        cols_data = {}
        for col in out['column_names']:
            # If the content is nested, need to break the flat name in a path list
            field_path = col.split('.')
            # Get content for the fields and make facts human readable
            content = _improve_facts_readability(hit['_source'], field_path, col)
            # To strip fields with whitespace in front
            try:
                old_content = content.strip()
            except:
                old_content = content

            # Substitute feature value with value highlighted by Elasticsearch
            if col in hl_config['fields'] and 'highlight' in hit:
                content = hit['highlight'][col][0] if col in hit['highlight'] else ''

            # Prettify and standardize highlights
            content, hl_data = _prettify_standardize_hls(name_to_inner_hits, col, content, old_content)
            # Append the final content of this col to the row
            if(row[col] == ''):
                row[col] = content
            cols_data[col] = {'highlight_data': hl_data, 'content': content, 'old_content': old_content}

        # Transliterate between cols
        # TODO In the future possibly better for translit_cols params to be passed data from given request
        _transliterate(cols_data, row)

        # Checks if user wants to see full text or short version
        for col in row:
            if 'show_short_version' in es_params.keys():
                row[col] = additional_option_cut_text(row[col], es_params['short_version_n_char'])

        out['aaData'].append(row.values())
        out['lag'] = time.time()-start_time
    return out

def _improve_facts_readability(content, paths, col):
    '''Changes texta_facts field content to be more human readable
        Get content for this field path:
        - Starts with the hit structure
        - For every field in field_path, retrieve the specific content
        - Repeat this until arrives at the last field
        - If the field in the field_path is not in this hit structure,
            make content empty (to allow dynamic mapping without breaking alignment)
        - Improve facts readability in searcher results if field is texta_facts'''

    for p in paths:
        if col == u'texta_facts' and p in content:
            new_content = []
            facts = ['{ "'+x["fact"]+'": "'+x["str_val"]+'"}' for x in sorted(content[p], key=lambda k: k['fact'])]
            fact_counts = Counter(facts)

            facts = sorted(list(set(facts)))
            facts_dict = [json.loads(x) for x in facts]
            for i, d in enumerate(facts_dict):
                for k in d:
                    # Make factnames bold for searcher results
                    if '<b>'+k+'</b>' not in new_content:
                        new_content.append('<b>'+k+'</b>')
                    new_content.append('    {}: {}'.format(d[k], fact_counts[facts[i]]))
            content = '\n'.join(new_content)
        else:
            content = content[p] if p in content else ''
    return content

def _prettify_standardize_hls(name_to_inner_hits, col, content, old_content):
    '''Applies prettified and standardized highlights to content'''
    hl_data = []
    # if name_to_inner_hits[col]:
    color_map = ColorPicker.get_color_map(keys={hit['fact'] for hit in name_to_inner_hits[col]})
    for inner_hit in name_to_inner_hits[col]:
        datum = {
            'spans': json.loads(inner_hit['spans']),
            'name': inner_hit['fact'],
            'category': '[{0}]'.format(inner_hit['hit_type']),
            'color': color_map[inner_hit['fact']]
        }

        if inner_hit['hit_type'] == 'fact_val':
            datum['value'] = inner_hit['str_val']
        hl_data.append(datum)

    content = Highlighter(average_colors=True, derive_spans=True,
                                additional_style_string='font-weight: bold;').highlight(
                                    old_content,
                                    hl_data,
                                    tagged_text=content)
    return content, hl_data


def _transliterate(cols_data, row, translit_cols=['text', 'translit', 'lemmas']):    
    # To get nested col value before '.'
    hl_cols = [x for x in cols_data if len(x.split('.')) > 1 and x.split('.')[-1] in translit_cols]
    # Transliterate the highlighting between hl_cols
    row = hl_transliterately(cols_data, row, hl_cols=hl_cols)
    return row


def _derive_hl_config(es_params):
    # Mark highlight the matching fields
    pre_tag = '<span class="[HL]" style="background-color:#FFD119">'
    post_tag = "</span>"
    hl_config = {"fields": {}, "pre_tags": [pre_tag], "post_tags": [post_tag]}
    for field in es_params:
        if 'match_field' in field and es_params['match_operator_'+field.split('_')[-1]] != 'must_not':
            f = es_params[field]
            hl_config['fields'][f] = {"number_of_fragments": 0}
    return hl_config


def _derive_name_to_inner_hits(inner_hits):
    name_to_inner_hits = defaultdict(list)
    for inner_hit_name, inner_hit in inner_hits.items():
        hit_type, _, _ = inner_hit_name.rsplit('_', 2)
        for inner_hit_hit in inner_hit['hits']['hits']:
            source = inner_hit_hit['_source']
            source['hit_type'] = hit_type
            name_to_inner_hits[source['doc_path']].append(source)
    return name_to_inner_hits