import bs4
import json
import bs4

def additional_option_cut_text(content, window_size):
    window_size = int(window_size)
    
    if not content:
        return ''
    
    if not isinstance(content, str):
        return content

    if '[HL]' in content:
        soup = bs4.BeautifulSoup(content,'lxml')
        html_spans = soup.find_all('span')
        html_spans_merged = []
        num_spans = len(html_spans)
        # merge together ovelapping spans
        for i,html_span in enumerate(html_spans):
            if not html_span.get('class')[0]:
                span_text = html_span.text
                span_tokens = span_text.split(' ')
                span_tokens_len = len(span_tokens)
                if i == 0:
                    if span_tokens_len > window_size:
                        new_text = u' '.join(span_tokens[-window_size:])
                        new_text = u'... {0}'.format(new_text)
                        html_span.string = new_text
                    html_spans_merged.append(str(html_span))
                elif i == num_spans-1:
                    if span_tokens_len > window_size:
                        new_text = u' '.join(span_tokens[:window_size])
                        new_text = u'{0} ...'.format(new_text)
                        html_span.string = new_text
                    html_spans_merged.append(str(html_span))
                else:
                    if span_tokens_len > window_size:
                        new_text_left = u' '.join(span_tokens[:window_size])
                        new_text_right = u' '.join(span_tokens[-window_size:])
                        new_text = u'{0} ...\n... {1}'.format(new_text_left,new_text_right)
                        html_span.string = new_text
                    html_spans_merged.append(str(html_span))
            else:
                html_spans_merged.append(str(html_span))

        return ''.join(html_spans_merged)
    else:
        return content


def collect_map_entries(map_):
    entries = []
    for key, value in map_.items():
        value['key'] = key
        entries.append(value)
    return entries


def get_daterange(es_m,field):
    min_val,max_val = es_m.get_extreme_dates(field)
    return {'min':min_val[:10],'max':max_val[:10]}


def get_fields_content(hit,fields):
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
            continue

        row[field] = field_content

    return row


def get_fields(es_m):
    texta_reserved = ['texta_facts']
    mapped_fields = es_m.get_mapped_fields()
    fields_with_facts = es_m.get_fields_with_facts()
    
    fields = []
    
    for mapped_field in mapped_fields.keys():
        data = json.loads(mapped_field)

        path = data['path']
        
        if path not in texta_reserved:
        
            path_list = path.split('.')

            label = '{0} --> {1}'.format(path_list[0], path_list[-1]) if len(path_list) > 1 else path_list[0]
            label = label.replace('-->', u'→')

            if data['type'] == 'date':
                data['range'] = get_daterange(es_m, path)

            data['label'] = label

            field = {'data': json.dumps(data), 'label': label, 'type': data['type']}
            fields.append(field)
        
            if path in fields_with_facts['fact']:
                data['type'] = 'facts'
                field = {'data': json.dumps(data), 'label': label + ' [fact_names]', 'type':'facts'}
                fields.append(field)

            if path in fields_with_facts['fact_str']:
                data['type'] = 'fact_str_val'
                field = {'data': json.dumps(data), 'label': label + ' [fact_text_values]', 'type':'facts'}
                fields.append(field)

            if path in fields_with_facts['fact_num']:
                data['type'] = 'fact_num_val'
                field = {'data': json.dumps(data), 'label': label + ' [fact_num_values]', 'type':'facts'}
                fields.append(field)
    
    # Sort fields by label
    fields = sorted(fields, key=lambda l: l['label'])
    
    return fields