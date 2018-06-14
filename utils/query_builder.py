from collections import defaultdict
import re

INNER_HITS_MAX_SIZE = 100

class QueryBuilder:

    def __init__(self, es_params):
        self.query = self._build(es_params)

    def _build(self, es_params):
        """ Build internal representation for queries using es_params

            A combined query is a dictionary D containing:

                D['main']   ->  the main elasticsearch query
                D['facts']  ->  the fact query

        """
        
        _combined_query = {"main": {"query": {"bool": {"should": [], "must": [], "must_not": []}}},
                           "facts": {"include": [], 'total_include': 0,
                                     "exclude": [], 'total_exclude': 0}}

        string_constraints = self._get_match_constraints(es_params)
        date_constraints = self._get_daterange_constraints(es_params)
        fact_constraints = self._get_fact_constraints(es_params)
        fact_val_constraints = self._get_fact_val_constraints(es_params)

        for string_constraint in string_constraints.values():

            match_field = string_constraint['match_field'] if 'match_field' in string_constraint else ''
            match_type = string_constraint['match_type'] if 'match_type' in string_constraint else ''
            match_slop = string_constraint["match_slop"] if 'match_slop' in string_constraint else ''
            match_operator = string_constraint['match_operator'] if 'match_operator' in string_constraint else ''

            query_strings = [s.replace('\r','') for s in string_constraint['match_txt'].split('\n')]
            query_strings = [s for s in query_strings if s]
            sub_queries = []

            for query_string in query_strings:
                synonyms = self._get_list_synonyms(query_string)
                # construct synonym queries
                synonym_queries = []
                for synonym in synonyms:
                    synonym_query = {}
                    if match_type == 'match':
                        # match query
                        sub_query = {'query': synonym, 'operator': 'and'}
                        synonym_query['match'] = {match_field: sub_query}
                    if match_type == 'match_phrase':
                        # match phrase query
                        sub_query = {'query': synonym, 'slop': match_slop}
                        synonym_query['match_phrase'] = {match_field: sub_query}
                    if match_type == 'match_phrase_prefix':
                        # match phrase prefix query
                        sub_query = {'query': synonym, 'slop': match_slop}
                        synonym_query['match_phrase_prefix'] = {match_field: sub_query}
                    synonym_queries.append(synonym_query)
                sub_queries.append({'bool': {'minimum_should_match': 1,'should': synonym_queries}})
            _combined_query["main"]["query"]["bool"]["should"].append({"bool": {match_operator: sub_queries}})
        _combined_query["main"]["query"]["bool"]["minimum_should_match"] = len(string_constraints)

        for date_constraint in date_constraints.values():
            date_range_start = {"range": {date_constraint['daterange_field']: {"gte": date_constraint['daterange_from']}}}
            date_range_end= {"range": {date_constraint['daterange_field']: {"lte": date_constraint['daterange_to']}}}
            _combined_query["main"]['query']['bool']['must'].append(date_range_start)
            _combined_query["main"]['query']['bool']['must'].append(date_range_end)

        total_include = 0
        for field_id, fact_constraint in fact_constraints.items():
            print(fact_constraints)
            _combined_query['main']['query']['bool']['must'].append({'nested': {'path': 'texta_facts', 'query':{'bool': {'must': []}}}})
            fact_query = _combined_query['main']['query']['bool']['must'][-1]['nested']['query']['bool']['must']

            fact_field = fact_constraint['fact_field'] if 'fact_field' in fact_constraint else ''
            fact_txt = fact_constraint['fact_txt'] if 'fact_txt' in fact_constraint else ''
            fact_operator = fact_constraint['fact_operator'] if 'fact_operator' in fact_constraint else ''
            query_strings = [s.replace('\r', '').strip() for s in fact_txt.split('\n')]
            query_strings = [s for s in query_strings if s]
            sub_queries = []
            # Add facts query to search in facts mapping
            fact_queries = []

            #fact_query.append({'match_phrase': {'texta_facts.fact': fact_field}})

            if query_strings:

                _combined_query['main']['query']['bool']['must'].append({'bool': {fact_operator: []}})
                fact_query = _combined_query['main']['query']['bool']['must'][-1]['bool'][fact_operator]


                for string_id, query_string in enumerate(query_strings):
                    fact_query.append(
                        {
                            'nested': {
                                'path': 'texta_facts',
                                'inner_hits': {
                                    'name': 'fact_' + str(field_id) + '_' + str(string_id),
                                    'size': INNER_HITS_MAX_SIZE
                                },
                                'query': {
                                    'bool': {
                                        'must': []
                                    }
                                }
                            }
                        }
                    )
                    nested_query = fact_query[-1]['nested']['query']['bool']['must']

                    nested_query.append({'term': {'texta_facts.doc_path': fact_field.lower()}})
                    nested_query.append({'term': {'texta_facts.fact': query_string}})

        for field_id, fact_val_constraint in fact_val_constraints.items():
            fact_operator = fact_val_constraint['operator']
            fact_field = fact_val_constraint['field']
            val_type = fact_val_constraint['type']

            _combined_query['main']['query']['bool']['must'].append({'bool': {fact_operator: []}})
            fact_val_query = _combined_query['main']['query']['bool']['must'][-1]['bool'][fact_operator]

            for constraint_id, value_constraint in fact_val_constraint['constraints'].items():
                fact_name = value_constraint['name']
                fact_value = value_constraint['value']
                fact_val_operator = value_constraint['operator']

                fact_val_query.append(
                    {
                        'nested': {
                            'path': 'texta_facts',
                            'inner_hits': {
                                'name': 'fact_val_'+str(field_id)+'_'+str(constraint_id),
                                'size': INNER_HITS_MAX_SIZE
                            },
                            'query': {
                                'bool': {
                                    'must': []
                                }
                            }
                        }
                    }
                )
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


        return _combined_query

    @staticmethod
    def _get_match_constraints(es_params):
        _constraints = {}
        for item in es_params:
            if 'match' in item:
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]
        return _constraints

    @staticmethod
    def _get_daterange_constraints(es_params):
        _constraints = {}
        for item in es_params:
            if item.startswith('daterange'):
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]
        return _constraints

    @staticmethod
    def _get_fact_constraints(es_params):
        _constraints = {}
        fact_val_constraint_keys = {u'type':None, u'val':None, u'op':None}
        for item in es_params:
            # This is hack. Think of something else instead to ignore graph size parameter.
            if 'fact' in item and 'graph' not in item:
                item = item.split('_')
                first_part = '_'.join(item[:2])
                second_part = item[2]
                if len(item) > 3:
                    fact_val_constraint_keys[second_part] = None
                if second_part not in _constraints:
                    _constraints[second_part] = {}
                _constraints[second_part][first_part] = es_params['_'.join(item)]

        QueryBuilder._remove_fact_val_fields(_constraints, fact_val_constraint_keys)

        return _constraints

    @staticmethod
    def _get_fact_val_constraints(es_params):
        constraints = defaultdict(lambda: {'constraints': defaultdict(dict)})
        for item in es_params:
            if 'fact_constraint' in item:
                key_parts = item.split('_')
                specifier, field_id = key_parts[2], key_parts[3]

                if specifier == 'type':
                    constraints[field_id]['type'] = es_params[item]
                else:
                    constraint_id = key_parts[4]
                    specifier_map = {'op': 'operator', 'val': 'value'}
                    constraints[field_id]['constraints'][constraint_id][specifier_map[specifier]] = es_params[item]
            elif 'fact_txt' in item:
                key_parts = item.split('_')

                if len(key_parts) == 3:  # Normal fact constraint
                    continue

                field_id, constraint_id = key_parts[2], key_parts[3]
                constraints[field_id]['constraints'][constraint_id]['name'] = es_params[item]
            elif 'fact_operator' in item:
                field_id = item.rsplit('_', 1)[1]
                constraints[field_id]['operator'] = es_params[item]
            elif 'fact_field' in item:
                field_id = item.rsplit('_', 1)[1]
                constraints[field_id]['field'] = es_params[item]

        constraints = dict(constraints)
        for constraint in constraints.values():
            constraint['constraints'] = dict(constraint['constraints'])

        QueryBuilder._remove_non_fact_val_fields(constraints)
        QueryBuilder._convert_fact_vals(constraints)

        return constraints

    @staticmethod
    def _remove_fact_val_fields(constraints, fact_val_keys):
        keys_to_remove = [key for key in fact_val_keys if key in constraints]
        for key in keys_to_remove:
            del constraints[key]

    @staticmethod
    def _remove_non_fact_val_fields(constraints):
        fields_to_remove = []
        for field_id in constraints:
            if len(constraints[field_id]['constraints']) == 0:
                fields_to_remove.append(field_id)
        for field_id in fields_to_remove:
            del constraints[field_id]

    @staticmethod
    def _convert_fact_vals(constraints):
        for constraint in constraints.values():
            if constraint['type'] == 'num':
                for sub_constraint in constraint['constraints'].values():
                    sub_constraint['value'] = float(sub_constraint['value'])

    @staticmethod
    def _get_list_synonyms(query_string):
        """ check if string is a concept or lexicon identifier
        """
        synonyms = []
        concept = re.search('^@C(\d)+-', query_string)
        lexicon = re.search('^@L(\d)+-', query_string)

        if concept:
            concept_id = int(concept.group()[2:-1])
            for term in TermConcept.objects.filter(concept=Concept.objects.get(pk=concept_id)):
                synonyms.append(term.term.term)
        elif lexicon:
            lexicon_id = int(lexicon.group()[2:-1])
            for word in Word.objects.filter(lexicon=Lexicon.objects.get(pk=lexicon_id)):
                synonyms.append(word.wrd)
        else:
            synonyms.append(query_string)

        return synonyms
