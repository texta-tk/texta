from utils.highlighter import Highlighter
import copy
from functools import wraps

def pass_by_value(func):
    @wraps(func)
    def decorator(*args, **kwargs):
        args = [copy.deepcopy(arg) for arg in args]
        kwargs = {key: copy.deepcopy(value) for key, value in kwargs.items()}

        return func(*args, **kwargs)

    return decorator

@pass_by_value
def transliterate_highlight_spans(highlight_data, source_text, target_text):
    """Transliterates the spans from cyr > latin or from latin > cyr
        wrapped by pass by value to dereference the variables.
    Arguments:
        highlight_data {list of dict} -- The highlight_data passed into the highlighter
        source_text {string} -- The source text from which the spans come from
        target_text {string} -- The target text to where the spans need to be corrected

    Returns:
        list of dict -- highlight_data but with corrected spans.
    """
    for dict_val in highlight_data:
        # such as {'category': u'[HL]" style="background-color:#FFD119', 'color': u'#FFD119', 'spans': [[40, 42]]}
        #such as [[39, 41]]
        for span in dict_val['spans']:
            #such as [39, 41]
            fact_words = source_text[span[0]:span[1]].split(' ')
            text_until_fact = source_text[:span[1]]
            words_until_fact = text_until_fact.split(' ')[:-len(fact_words)]

            translit_words = target_text.split(' ')
            translit_words_until_fact = translit_words[:len(words_until_fact)]
            translit_facts_words = translit_words[len(translit_words_until_fact):len(translit_words_until_fact) + len(fact_words)]
            translit_facts_spans = [len(' '.join(translit_words_until_fact)) + 1, len(' '.join(translit_words_until_fact)) + len(' '.join(translit_facts_words)) + 1]
            # if span was supposed to be 0
            if translit_facts_spans[0] == 1:
                translit_facts_spans[0] = 0
                translit_facts_spans[1] = translit_facts_spans[1] - 1
            dict_val['spans'] = [translit_facts_spans]

    return highlight_data

# def highlight_transliterately(col, row, highlight_data, content, hit):
#     """Highlights the search result of text.texct in text.translit and vice versa

#     Arguments:
#         col {string} -- The column name
#         row {OrderedDict} -- The row content for a column
#         highlight_data {list of dict} -- The highlight_data passed into the highlighter
#         content {string} -- The content containing the spans in HTML format
#         hit {dict} -- A dict containing the hit results

#     Returns:
#         row {OrderedDict} -- The row now with transliterate highlighting on both .text and .translit
#     """
#     print(col, highlight_data)
#     if (col == 'text.translit' and highlight_data != []) or (col == 'text.text' and highlight_data != []):
#         if col == 'text.translit':
#             highlight_data = transliterate_highlight_spans(highlight_data, hit['_source']['text']['translit'], hit['_source']['text']['text'])
#             content_hl_trans = Highlighter(average_colors=True, derive_spans=True,
#                                     additional_style_string='font-weight: bold;').highlight(
#                                         hit['_source']['text']['text'],
#                                         highlight_data,
#                                         tagged_text=content)
#             row['text.text'] = content_hl_trans

#         elif col == 'text.text':
#             highlight_data = transliterate_highlight_spans(highlight_data, hit['_source']['text']['text'], hit['_source']['text']['translit'])
#             content_hl_trans = Highlighter(average_colors=True, derive_spans=True,
#                                     additional_style_string='font-weight: bold;').highlight(
#                                         hit['_source']['text']['translit'],
#                                         highlight_data,
#                                         tagged_text=content)
#             row['text.translit'] = content_hl_trans

#     return row

def highlight_transliterately(col, row, highlight_data, content, hit, hl_cols=['text.text', 'text.translit', 'text.lemmas']):
    """Highlights the search result of text.text in text.translit and vice versa

    Arguments:
        col {string} -- The column name
        row {OrderedDict} -- The row content for a column
        highlight_data {list of dict} -- The highlight_data passed into the highlighter
        content {string} -- The content containing the spans in HTML format
        hit {dict} -- A dict containing the hit results
        hl_cols {list} -- A list of strings representing the col names of the cols where to display the search result
    Returns:
        row {OrderedDict} -- The row now with transliterate highlighting on both .text and .translit
    """

    # NOTE when doing multi search, like text(text) 'v' and text(translit) 'na' then results are replacing e/o.
    # NOTE something wrong with lemmas transliteration.
    print('CALLED')
    #print(col, highlight_data)
    if (any(col == x for x in hl_cols) and highlight_data != []):
        hl_data = [highlight_data]
        for i, hl_col in enumerate([x for x in hl_cols if x != col]):
            col_name = col.split('.')[1]
            hl_col_name = hl_col.split('.')[1]
            import pdb; pdb.set_trace()
            new_highlight_data = transliterate_highlight_spans(hl_data[i], hit['_source']['text'][col_name], hit['_source']['text'][hl_col_name])
            import pdb; pdb.set_trace()
            hl_data.insert(0, new_highlight_data) # Insert to index 0
            content_hl_trans = Highlighter(average_colors=True, derive_spans=True,
                                    additional_style_string='font-weight: bold;').highlight(
                                        hit['_source']['text'][hl_col_name],
                                        new_highlight_data,
                                        tagged_text=content)
            row[hl_col] = content_hl_trans

    return row
            # if col == 'text.translit':
            #     highlight_data = transliterate_highlight_spans(highlight_data, hit['_source']['text']['translit'], hit['_source']['text']['text'])
            #     content_hl_trans = Highlighter(average_colors=True, derive_spans=True,
            #                             additional_style_string='font-weight: bold;').highlight(
            #                                 hit['_source']['text']['text'],
            #                                 highlight_data,
            #                                 tagged_text=content)
            #     row['text.text'] = content_hl_trans

            # elif col == 'text.text':
            #     highlight_data = transliterate_highlight_spans(highlight_data, hit['_source']['text']['text'], hit['_source']['text']['translit'])
            #     content_hl_trans = Highlighter(average_colors=True, derive_spans=True,
            #                             additional_style_string='font-weight: bold;').highlight(
            #                                 hit['_source']['text']['translit'],
            #                                 highlight_data,
            #                                 tagged_text=content)
            #     row['text.translit'] = content_hl_trans

