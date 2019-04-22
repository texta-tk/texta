import bs4
import json
import bs4
from collections import Counter


def additional_option_cut_text(content, window_size, count=0):
    window_size = int(window_size)

    if not content:
        return ''

    if not isinstance(content, str):
        return content

    if '[HL]' in content:
        soup = bs4.BeautifulSoup(content, 'lxml')
        html_spans = soup.find_all('span')
        html_spans_merged = []
        num_spans = len(html_spans)
        # merge together overlapping spans
        for i, html_span in enumerate(html_spans):
            if not html_span.get('class')[0]:
                span_text = html_span.text
                span_tokens = span_text.split(' ')
                span_tokens_len = len(span_tokens)
                if i == 0:
                    if span_tokens_len > window_size:
                        new_text = u' '.join(span_tokens[-window_size:])
                        new_text = u' {0}'.format(new_text)

                        html_span.string = new_text
                        # cant append to None so just insert to first pos
                        html_span.insert(0, _make_html_element(' '.join(span_tokens[:-window_size]), soup, count))

                    html_spans_merged.append(str(html_span))
                elif i == num_spans - 1:
                    if span_tokens_len > window_size:
                        new_text = u' '.join(span_tokens[:window_size])
                        new_text = u'{0} '.format(new_text)

                        html_span.string = new_text
                        html_span.append(_make_html_element(' '.join(span_tokens[window_size:]), soup, count))

                    html_spans_merged.append(str(html_span))
                else:
                    if span_tokens_len > window_size:
                        new_text_left = u' '.join(span_tokens[:window_size])
                        new_text_right = u' '.join(span_tokens[-window_size:])
                        middle_text = u' '.join(span_tokens[window_size:-window_size])

                        html_span.string = new_text_left

                        # Sometimes the window_size and new_text_left, new_text_right together are the exact same length
                        # That would create empty ... fields
                        if middle_text != '':
                            html_span.append(_make_html_element(middle_text, soup, count))

                        html_span.append(new_text_right)
                    html_spans_merged.append(str(html_span))
            else:
                html_spans_merged.append(str(html_span))
        return_str = ''.join(html_spans_merged)

        return return_str
    else:
        return content


def _make_html_element(text, soup, count):
    new_tag = soup.new_tag('show-short-version')
    new_tag.attrs['data-tracker-id'] = count
    new_tag.attrs['data-text'] = ' ' + text + ' '
    new_tag.attrs['data-placeholder-string'] = '...'
    return new_tag


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        value['key'] = key
        entries.append(value)
    return entries


def get_daterange(es_m, field):
    min_val, max_val = es_m.get_extreme_dates(field)
    return {'min': min_val[:10], 'max': max_val[:10]}


def get_fields_content(hit, fields):
    row = {}
    for field in fields:
        if 'highlight' in hit:
            field_content = hit['highlight']
        else:
            field_content = hit['_source']

        try:
            for field_element in field.split('.'):
                field_content = field_content[field_element]
        except KeyError:
            field_content = ''

        if type(field_content) == list:
            field_content = improve_facts_readability(field_content)

        # remove HTML
        field_content = bs4.BeautifulSoup(field_content).get_text()
        row[field] = field_content

    return row


def improve_facts_readability(content, join_with='\n', indent_with='    '):
    '''Changes texta_facts field content to be more human readable'''
    new_content = []

    facts = [(x["fact"], x["str_val"]) for x in sorted(content, key=lambda k: k['fact'])]

    fact_counts = Counter(facts)
    facts = sorted(list(set(facts)))

    for ind, (name, val) in enumerate(facts):
        if name not in new_content:
            new_content.append(name)
        new_content.append('{}{}: {}'.format(indent_with, val, fact_counts[facts[ind]]))
    content = join_with.join(new_content)

    return content


def get_fields(es_m):
    texta_reserved = ['texta_facts']
    mapped_fields = es_m.get_mapped_fields()
    fields_with_facts = es_m.get_fields_with_facts()

    fields = []

    for mapped_field in mapped_fields.keys():
        data = json.loads(mapped_field)

        path = data['path']

        if path not in texta_reserved:
            label = path.replace('.', '→')

            if data['type'] == 'date':
                data['range'] = get_daterange(es_m, path)

            data['label'] = label

            field = {'data': json.dumps(data), 'label': label, 'type': data['type']}
            fields.append(field)

            if path in fields_with_facts['fact']:
                data['type'] = 'facts'
                field = {'data': json.dumps(data), 'label': label + ' [fact_names]', 'type': 'facts'}
                fields.append(field)

            if path in fields_with_facts['fact_str']:
                data['type'] = 'fact_str_val'
                field = {'data': json.dumps(data), 'label': label + ' [fact_text_values]', 'type': 'facts'}
                fields.append(field)

            if path in fields_with_facts['fact_num']:
                data['type'] = 'fact_num_val'
                field = {'data': json.dumps(data), 'label': label + ' [fact_num_values]', 'type': 'facts'}
                fields.append(field)

    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])

    return fields
