import json
import time
import warnings
from collections import OrderedDict, defaultdict

import dictor
from bs4 import BeautifulSoup

from searcher.view_functions.build_search.translit_highlighting import hl_transliterately
from searcher.view_functions.general.searcher_utils import additional_option_cut_text, improve_facts_readability
from texta.settings import FACT_FIELD
from utils.generic_helpers import extract_element_from_json
from utils.highlighter import ColorPicker, Highlighter

warnings.filterwarnings("ignore", category=UserWarning, module='bs4')


def execute_search(es_m, es_params):
    start_time = time.time()
    out = {'column_names': [], 'aaData': [], 'iTotalRecords': 0, 'iTotalDisplayRecords': 0, 'lag': 0}
    # DEFINING THE EXAMPLE SIZE
    es_m.set_query_parameter('from', es_params['examples_start'])
    es_m.set_query_parameter('size', es_params['num_examples'])

    # HIGHLIGHTING THE MATCHING FIELDS
    hl_config = _derive_hl_config(es_params)
    es_m.set_query_parameter('highlight', hl_config)
    response = es_m.search()
    out['iTotalRecords'] = response['hits']['total']
    out['iTotalDisplayRecords'] = response['hits']['total']  # number of docs

    if int(out['iTotalDisplayRecords']) > 10000:  # Allow less pages if over page limit
        out['iTotalDisplayRecords'] = '10000'
    out['column_names'] = es_m.get_column_names(facts=True)  # get columns names from ES mapping

    strip_html = True
    if 'html_stripping' in es_params:
        strip_html = False

    hits = response['hits']['hits']
    # hits = es_m.remove_html_from_hits(hits)
    counter = 0
    for hit in hits:
        hit_id = str(hit['_id'])
        hit['_source']['_es_id'] = hit_id
        row = OrderedDict([(x, '') for x in out['column_names']])  # OrderedDict to remember column names with their content

        inner_hits = hit['inner_hits'] if 'inner_hits' in hit else {}
        name_to_inner_hits = _derive_name_to_inner_hits(inner_hits)

        # Fill the row content respecting the order of the columns
        cols_data = {}
        for col in out['column_names']:
            # If the content is nested, need to break the flat name in a path list

            field_path = col.split('.')

            # Get content for the fields and make facts human readable
            # Possible outcomes for a field:
            #   Normal field value - covered by dictor.
            #   Object field value - covered by dictor
            #   List of normal values - check for list and element type
            #   List of objects - check for list and dict element, get the key values.

            content = hit['_source']
            if col == FACT_FIELD and col in hit['_source']:
                content = improve_facts_readability(hit['_source'][col])
            else:

                # When the value of the field is a normal field or object field.
                if dictor.dictor(content, col, default=""):
                    content = dictor.dictor(content, col, default="")
                else:
                    content = extract_element_from_json(content, field_path)
                    content = [str(value) for value in content if value is not None]
                    content = "\n".join(content) if content else None

            content = str(content) if content else ""

            if strip_html:
                soup = BeautifulSoup(content, "lxml")
                content = soup.get_text()
            # To strip fields with whitespace in front
            old_content = content.strip()

            # Substitute feature value with value highlighted by Elasticsearch
            if col in hl_config['fields'] and 'highlight' in hit:
                content = hit['highlight'][col][0] if col in hit['highlight'] else ''

            # Prettify and standardize highlights
            content, hl_data = _prettify_standardize_hls(name_to_inner_hits, col, content, old_content)
            # Append the final content of this col to the row
            if (row[col] == ''):
                row[col] = content
            cols_data[col] = {'highlight_data': hl_data, 'content': content, 'old_content': old_content}

        # Transliterate between cols
        # TODO In the future possibly better for translit_cols params to be passed data from given request
        _transliterate(cols_data, row)

        # Checks if user wants to see full text or short version
        if 'show_short_version' in es_params.keys():
            for col in row:
                row[col] = additional_option_cut_text(row[col], es_params['short_version_n_char'], count=counter)
        out['aaData'].append([hit_id] + list(row.values()))
        out['lag'] = time.time() - start_time
        counter += 1
    return out


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
            'color': color_map[inner_hit['fact']],
        }

        if 'description' in inner_hit:
            datum['description'] = inner_hit['description']

        if inner_hit['hit_type'] in ['fact_val']:
            datum['value'] = inner_hit['str_val']

        hl_data.append(datum)

    content = Highlighter(average_colors=True, derive_spans=True,
                          additional_style_string='font-weight: bold;').highlight(
        str(old_content),
        hl_data,
        tagged_text=str(content))
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
        if 'match_field' in field and es_params['match_operator_' + field.split('_')[-1]] != 'must_not':
            f = es_params[field]
            for sub_f in f.split(','):
                hl_config['fields'][sub_f] = {"number_of_fragments": 0}
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
