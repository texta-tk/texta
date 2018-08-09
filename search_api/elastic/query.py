from copy import deepcopy


class Query(object):

    def __init__(self, query=None):
        if not query:
            self._query = {'query': {'bool': {'should': [], 'must': [], 'must_not': []}}}
        else:
            self._query = query

    def set_parameter(self, name, value):
        self._query[name] = value

    def add_string_constraints(self, constraints):
        for constraint in constraints:
            field = constraint.get('field', '')
            query_strings = constraint.get('strings', [])

            if not field or not query_strings:
                continue

            type_ = constraint.get('type', 'match_phrase')
            slop = constraint.get('slop', 0)
            operator = constraint.get('operator', 'must')

            sub_queries = []

            for query_string in query_strings:
                sub_query_matcher = {
                    'match': {
                        'match': {
                            field: {'query': query_string, 'operator': 'and'}
                        }
                    },
                    'match_phrase': {
                        'match_phrase': {
                            field: {'query': query_string, 'slop': slop}
                        }
                    },
                    'match_phrase_prefix': {
                        'match_phrase_prefix': {
                            field: {'query': query_string, 'slop': slop}
                        }
                    }
                }[type_]

                sub_query = {'bool': {'minimum_should_match': 1, 'should': [sub_query_matcher]}}
                sub_queries.append(sub_query)

            self._query['query']['bool']['should'].append({'bool': {operator: sub_queries}})

        self._query['query']['bool']['minimum_should_match'] = len(constraints)

    def add_date_constraints(self, constraints):
        for constraint in constraints:
            field = constraint.get('field', None)
            start = constraint.get('start', None)
            end = constraint.get('end', None)

            if not (field and (start or end)):
                continue

            date_range = {"range": {field: {}}}
            if start:
                date_range['range'][field]['gte'] = start
            if end:
                date_range['range'][field]['gte'] = end

            self._query['query']['bool']['must'].append(date_range)

    def add_fact_constraints(self, constraints):
        for constraint_id, constraint in enumerate(constraints):

            field = constraint.get('field', '')
            operator = constraint.get('operator', 'must')
            query_strings = constraint.get('strings', [])

            if query_strings:
                self._query['query']['bool']['must'].append({'bool': {operator: []}})
                fact_query = self._query['query']['bool']['must'][-1]['bool'][operator]

                for string_id, query_string in enumerate(query_strings):
                    fact_query.append({'nested': {'path': 'texta_facts', 'inner_hits': {
                        'name': 'fact_' + str(constraint_id) + '_' + str(string_id)},
                                                  'query': {'bool': {'must': []}}}})
                    nested_query = fact_query[-1]['nested']['query']['bool']['must']

                    nested_query.append({'match': {'texta_facts.doc_path': field.lower()}})
                    nested_query.append({'match': {'texta_facts.fact': query_string}})

    def add_fact_val_constraints(self, constraints):
        for constraint_id, constraint in enumerate(constraints):
            fact_operator = constraint.get('operator', 'must')
            fact_field = constraint['field']
            val_type = constraint['type']

            self._query['query']['bool']['must'].append({'bool': {fact_operator: []}})
            fact_val_query = self._query['query']['bool']['must'][-1]['bool'][fact_operator]

            for sub_constraint_id, sub_constraint in enumerate(constraint['constraints']):
                fact_name = sub_constraint['name']
                fact_value = sub_constraint['value']
                fact_val_operator = sub_constraint['operator']

                fact_val_query.append({'nested': {'path': 'texta_facts', 'inner_hits':{'name':'fact_val_'+str(constraint_id)+'_'+str(sub_constraint_id)},
                                                  'query': {'bool': {'must': []}}}})
                nested_query = fact_val_query[-1]['nested']['query']['bool']['must']
                nested_query.append({'match': {'texta_facts.fact': fact_name}})
                nested_query.append({'match': {'texta_facts.doc_path': fact_field}})

                if val_type == 'str':
                    if fact_val_operator == '=':
                        nested_query.append({'match': {'texta_facts.str_val': fact_value}})
                    elif fact_val_operator == '!=':
                        nested_query = fact_val_query[-1]['nested']['query']['bool']
                        nested_query['must_not'] = [{'match': {'texta_facts.str_val': fact_value}}]

                elif val_type == 'num':
                    if fact_val_operator == '=':
                        nested_query.append({'term': {'texta_facts.num_val': fact_value}})
                    elif fact_val_operator == '!=':
                        nested_query = fact_val_query[-1]['nested']['query']['bool']
                        nested_query['must_not'] = [{'match': {'texta_facts.num_val': fact_value}}]
                    else:
                        operator = {'<': 'lt', '<=': 'lte', '>': 'gt', '>=': 'gte'}[fact_val_operator]
                        nested_query.append({'range': {'texta_facts.num_val': {operator: fact_value}}})

    def generate(self):
        return self._query

    def copy(self):
        return Query(self._query)