
def extract_constraints(query):
    """Extracts GUI search field values from Elasticsearch query.
    """
    constraints = []

    if 'should' in query['main']['query']['bool'] and query['main']['query']['bool']['should']:
        for raw_constraint in query['main']['query']['bool']['should']:
            constraints.append(_extract_string_constraint(raw_constraint))


    if 'must' in query['main']['query']['bool'] and query['main']['query']['bool']['must']:
        range_constraints = []

        for raw_constraint_idx, raw_constraint in enumerate(query['main']['query']['bool']['must']):
            if 'range' in raw_constraint:
                range_constraints.append((raw_constraint_idx, raw_constraint))
            elif 'bool' in raw_constraint:
                if list(raw_constraint['bool'].values())[0][0]['nested']['inner_hits']['name'].startswith('fact_val'):   # fact val query
                    constraints.append(_extract_fact_val_constraint(raw_constraint))
                else:   # fact query
                    constraints.append(_extract_fact_constraint(raw_constraint))

        constraints.extend(_extract_date_constraints(range_constraints))

    return constraints


def _extract_string_constraint(raw_constraint):
    operator = list(raw_constraint['bool'].keys())[0]
    field = None
    match_type = None
    constraint_content = []
    slop = None

    for entry in raw_constraint['bool'][operator]:
        constraint_details = list(entry['bool']['should'])[0]
        match_type = constraint_details['multi_match']['type']
        field = ','.join(constraint_details['multi_match']['fields'])
        content = constraint_details['multi_match']['query']
        # Match: word does not need a slop
        slop = int(constraint_details['multi_match']['slop']) if match_type != 'match' else 0
        constraint_content.append(content)
    return {
        'constraint_type': 'string',
        'operator': operator,
        'field': field,
        'match_type': match_type,
        'content': constraint_content,
        'slop': slop
    }


def _extract_date_constraints(range_constraint_idx_range_constraint_pairs):
    date_ranges = []

    new_range = None
    last_idx = -1
    last_comparative_operator = 'lte'
    last_field = None

    for range_constraint_idx, range_constraint in range_constraint_idx_range_constraint_pairs:
        current_field = list(range_constraint['range'].keys())[0]
        if 'gte' in range_constraint['range'][current_field]:
            if last_field is not None:
                date_ranges.append(new_range)
            new_range = {
                'start_date': range_constraint['range'][current_field]['gte'],
                'field': current_field,
                'constraint_type': 'date'
            }

            last_comparative_operator = 'gte'
        elif 'lte' in range_constraint['range'][current_field]:
            if not (range_constraint_idx - 1 == last_idx and last_comparative_operator == 'gte' and
                            current_field == last_field) and last_field is not None:
                date_ranges.append(new_range)
            elif last_field is None:
                new_range = {
                    'field': current_field,
                    'constraint_type': 'date'
                }

            new_range['end_date'] = range_constraint['range'][current_field]['lte']

            last_comparative_operator = 'lte'

        last_field = current_field
        last_idx = range_constraint_idx

    if new_range:
        date_ranges.append(new_range)

    return date_ranges


def _extract_fact_constraint(raw_constraint):
    operator = list(raw_constraint['bool'].keys())[0]
    content = []
    field = None

    for entry in raw_constraint['bool'][operator]:
        field = list(entry['nested']['query']['bool']['must'][0]['term'].values())[0]
        content.append(list(entry['nested']['query']['bool']['must'][1]['term'].values())[0])

    return {
        'constraint_type': 'facts',
        'operator': operator,
        'field': field,
        'content': content
    }


def _extract_fact_val_constraint(raw_constraint):
    operator = list(raw_constraint['bool'].keys())[0]
    field = None
    sub_constraints = []

    for entry in raw_constraint['bool'][operator]:
        fact_name = None
        fact_val_operator = None
        fact_val = None
        constraint_type = None

        for sub_entry in entry['nested']['query']['bool']['must']:
            if 'texta_facts.doc_path' in sub_entry['match']:
                field = sub_entry['match']['texta_facts.doc_path']
            elif 'texta_facts.fact' in sub_entry['match']:
                fact_name = sub_entry['match']['texta_facts.fact']
            elif 'texta_facts.str_val' in sub_entry['match']:
                fact_val = sub_entry['match']['texta_facts.str_val']
                fact_val_operator = '='
                constraint_type = 'str_fact_val'
            elif 'texta_facts.num_val' in sub_entry['match']:
                fact_val = sub_entry['match']['texta_facts.num_val']
                fact_val_operator = '='
                constraint_type = 'num_fact_val'

        if fact_val == None:
            if 'must_not' in entry['nested']['query']['bool']:
                if 'texta_facts.str_val' in entry['nested']['query']['bool']['must_not'][0]['match']:
                    fact_val = entry['nested']['query']['bool']['must_not'][0]['match']['texta_facts.str_val']
                    fact_val_operator = '!='
                    constraint_type = 'str_fact_val'
                else:
                    fact_val = entry['nested']['query']['bool']['must_not'][0]['match']['texta_facts.num_val']
                    fact_val_operator = '!='
                    constraint_type = 'num_fact_val'

        sub_constraints.append({
            'fact_name': fact_name,
            'fact_val': fact_val,
            'fact_val_operator': fact_val_operator
        })

    return {
        'constraint_type': constraint_type,
        'operator': operator,
        'field': field,
        'sub_constraints': sub_constraints
    }