from utils.highlighter import Highlighter
import copy
from functools import wraps

def pass_by_value(func):
    '''deepcopy value decorator'''
    @wraps(func)
    def decorator(*args, **kwargs):
        args = [copy.deepcopy(arg) for arg in args]
        kwargs = {key: copy.deepcopy(value) for key, value in kwargs.items()}

        return func(*args, **kwargs)

    return decorator

@pass_by_value
def transliterate_hl_spans(hl_data, source_text, target_text):
    """Transliterates the spans from source > target
        wrapped by pass by value to dereference the variables.
    Arguments:
        hl_data {list of dict} -- The highlight data passed into the highlighter
        source_text {string} -- The source text from which the s,pans come from
        target_text {string} -- The target text to where the spans need to be corrected

    Returns:
        list of dict -- hl_data but with corrected spans.
    """

    for dict_val in hl_data:
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
    return hl_data

def hl_transliterately(cols_data, row, hl_cols=['text.text', 'text.translit', 'text.lemmas']):
    """Highlights the search result of text.text in text.translit and vice versa

    Arguments:
        cols_data {dict} -- Dict containing the col data, like {'text.text': {'highlight_data': hl_data, 'content': content, 'old_content': old_content}}
            col {string} -- The column name
            hl_data {list of dict} -- The highlight data passed into the highlighter
            content {string} -- The content containing the spans in HTML format
            old_content {string} -- The content without the HTML data.
        row {OrderedDict} -- The row content for a column
        hl_cols {list} -- A list of strings representing the col names of the cols where to display the search result
    Returns:
        row {OrderedDict} -- The row now with transliterate highlighting on both .text and .translit
    """
    # Filter translit to be only between hl_cols fields
    cols_with_hl_data = {x for x in cols_data if cols_data[x]['highlight_data'] != [] and x in hl_cols}
    cols_data_joined = cols_data

    for col in cols_with_hl_data:
        for target_col in [x for x in cols_with_hl_data if x != col]:
            joined_hl_data = cols_data[target_col]['highlight_data']
            translit_hl_data = transliterate_hl_spans(cols_data[col]['highlight_data'], cols_data[col]['old_content'], cols_data[target_col]['old_content'])
            for x in  translit_hl_data:
                x['color'] = '#4286f4'
                joined_hl_data.append(x)
            cols_data_joined[target_col]['highlight_data'] = joined_hl_data


    for col in cols_with_hl_data:
        hl_data = [cols_data_joined[col]['highlight_data']]
        for i, hl_col in enumerate([x for x in hl_cols if x != col]):
            new_hl_data = transliterate_hl_spans(hl_data[i], cols_data_joined[col]['old_content'], cols_data_joined[hl_col]['old_content'])
            hl_data.insert(0, new_hl_data) # Insert to index 0
            content_hl_trans = Highlighter(average_colors=True, derive_spans=True,
                                    additional_style_string='font-weight: bold;').highlight(
                                        str(cols_data_joined[hl_col]['old_content']),
                                        new_hl_data,
                                        tagged_text=str(cols_data_joined[hl_col]['old_content']))
            row[hl_col] = content_hl_trans

    return row
