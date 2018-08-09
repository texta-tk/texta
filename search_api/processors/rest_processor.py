import json
from permission_admin.models import Dataset
from account.models import Profile


class RestProcessor(object):

    @staticmethod
    def process_searcher(django_request):
        if django_request.method == 'GET':
            return RestProcessor._process_searcher_get(django_request)
        elif django_request.method == 'POST':
            return RestProcessor._process_searcher_post(django_request)

    @staticmethod
    def process_aggregator(django_request):
        if django_request.method == 'GET':
            return RestProcessor._process_aggregator_get(django_request)
        elif django_request.method == 'POST':
            return RestProcessor._process_aggregator_post(django_request)

    @staticmethod
    def _process_searcher_get(django_request):
        dataset_id = django_request.GET['dataset']
        dataset = Dataset.objects.get(pk=dataset_id)

        index = dataset.index
        mapping = dataset.mapping

        fields = django_request.GET.get('fields', "[]")
        constraints = django_request.GET.get('constraints', "[]")
        parameters = django_request.GET.get('parameters', "[]")
        scroll = django_request.GET.get('scroll', 'false')
        scroll_id = django_request.GET.get('scroll_id', None)

        return {
            'dataset': dataset_id,
            'index': index,
            'mapping': mapping,
            'fields': json.loads(fields),
            'constraints': json.loads(constraints),
            'parameters': json.loads(parameters),
            'scroll': True if scroll.lower() == 'true' else False,
            'scroll_id': scroll_id,
        }

    @staticmethod
    def _process_searcher_post(django_request):
        try:
            processed_query = json.loads(django_request.body.decode())
        except:
            raise Exception('Malformed JSON syntax.')

        try:
            auth_token = processed_query['auth_token']
        except:
            raise Exception('Authentication token missing.')

        try:
            profile = Profile.objects.get(auth_token = auth_token)
        except:
            raise Exception('Invalid authentication token.')

        Validator.validate_search_data(processed_query, profile.user)

        dataset_id = int(processed_query['dataset'])
        dataset = Dataset.objects.get(pk=dataset_id)

        for key in ['fields', 'constraints', 'parameters']:
            if key not in processed_query:
                processed_query[key] = []

        processed_query['dataset'] = dataset_id
        processed_query['index'] = dataset.index
        processed_query['mapping'] = dataset.mapping

        return processed_query

    @staticmethod
    def _process_aggregator_get(django_request):
        pass

    @staticmethod
    def _process_aggregator_post(django_request):
        try:
            processed_query = json.loads(django_request.body.decode())
        except:
            raise Exception('Malformed JSON syntax.')

        try:
            auth_token = processed_query['auth_token']
        except:
            raise Exception('Authentication token missing.')

        try:
            profile = Profile.objects.get(auth_token = auth_token)
        except:
            raise Exception('Invalid authentication token.')

        Validator.validate_aggregation_data(processed_query)

        for search_idx, search in enumerate(processed_query['searches']):
            Validator.validate_search_data(search, profile.user, search_idx)

            dataset_id = int(search['dataset'])
            dataset = Dataset.objects.get(pk=dataset_id)

            for key in ['fields', 'constraints', 'parameters']:
                if key not in search:
                    search[key] = []

            search['dataset'] = dataset_id
            search['index'] = dataset.index
            search['mapping'] = dataset.mapping

        return processed_query


class Validator(object):

    valid_fields = {
        'string': {
            'field': {'mandatory': True, 'values': None},
            'operator': {'mandatory': False, 'values': ['must', 'should', 'must_not']},
            'type': {'mandatory': False, 'values': ['match', 'match_phrase', 'match_phrase_prefix']},
            'slop': {'mandatory': False, 'values': None},
            'strings': {'mandatory': True, 'values': None},
            'class': {'mandatory': True, 'values': None}
        },
        'date': {
            'field': {'mandatory': True, 'values': None},
            'class': {'mandatory': True, 'values': None},
            'start': {'mandatory': False, 'values': None},
            'end': {'mandatory': False, 'values': None}
        },
        'fact': {
            'field': {'mandatory': True, 'values': None},
            'operator': {'mandatory': False, 'values': ['must', 'should', 'must_not']},
            'class': {'mandatory': True, 'values': None},
            'strings': {'mandatory': True, 'values': None}
        },
        'fact_val': {
            'field': {'mandatory': True, 'values': None},
            'operator': {'mandatory': False, 'values': ['must', 'should', 'must_not']},
            'type': {'mandatory': True, 'values': ['str', 'num']},
            'constraints': {'mandatory': True, 'values': None},
            'class': {'mandatory': True, 'values': None}
        }
    }

    valid_aggregation_fields = {
        'daterange': {
            'field': {'mandatory': True, 'values': None},
            'type': {'mandatory': True, 'values': None},
            'start': {'mandatory': True, 'values': None},
            'end': {'mandatory': True, 'values': None},
            'frequency': {'mandatory': True, 'values': ['raw_frequency', 'relative_frequency']},
            'interval': {'mandatory': True, 'values': ['day', 'week', 'month', 'quarter', 'year']}
        },
        'string': {
            'field': {'mandatory': True, 'values': None},
            'type': {'mandatory': True, 'values': None},
            'sort_by': {'mandatory': True, 'values': ['terms', 'significant_terms', 'significant_text']}
        },
        'fact': {
            'field': {'mandatory': True, 'values': None},
            'type': {'mandatory': True, 'values': None},
            'sort_by': {'mandatory': True, 'values': ['terms', 'significant_terms', 'significant_text']}
        },
        'fact_str': {
            'field': {'mandatory': True, 'values': None},
            'type': {'mandatory': True, 'values': None},
            'sort_by': {'mandatory': True, 'values': ['terms', 'significant_terms', 'significant_text']}
        },
        'fact_num': {
            'field': {'mandatory': True, 'values': None},
            'type': {'mandatory': True, 'values': None},
            'sort_by': {'mandatory': True, 'values': ['terms', 'significant_terms', 'significant_text']}
        }
    }

    @staticmethod
    def validate_aggregation_data(data_dict):
        if 'searches' not in data_dict:
            raise Exception('Missing "searches" attribute.')

        if not isinstance(data_dict['searches'], list):
            raise Exception('"searches" attribute value is not a list.')

        if not data_dict['searches']:
            raise Exception('"searches" list is empty.')

        if 'aggregation' not in data_dict:
            raise Exception('Missing "aggregation" attribute.')

        Validator._validate_aggregations(data_dict['aggregation'])

    @staticmethod
    def _validate_aggregations(aggregations):
        if not isinstance(aggregations, list):
            raise Exception('"aggregation" attribute value is not a list.')

        if not aggregations:
            raise Exception('No aggregation levels defined in "aggregation" attribute.')

        for aggregation_idx, aggregation in enumerate(aggregations):
            if 'type' not in aggregation:
                raise Exception('"type" attribute missing for aggregation {0}.'.format(aggregation_idx))

            if aggregation['type'] not in Validator.valid_aggregation_fields:
                raise Exception('"type" attribute for aggregation {0} must have one of the following values: {1}.'.format(
                    aggregation_idx, [type_ for type_ in Validator.valid_aggregation_fields]
                ))

            type_ = aggregation['type']
            valid_aggregation_fields = Validator.valid_aggregation_fields[type_]

            for field in aggregation:
                if field not in valid_aggregation_fields:
                    raise Exception('"{0}" is not a valid attribute for aggregation {1}.'.format(
                        field, aggregation_idx
                    ))

            for field in valid_aggregation_fields:
                field_data = valid_aggregation_fields[field]
                if field_data['mandatory'] and field not in aggregation:
                    raise Exception('Aggregation {0} is missing mandatory attribute "{1}".'.format(
                        aggregation_idx, field
                    ))
                if field_data['values'] and field in aggregation and aggregation[field] not in field_data['values']:
                    raise Exception('Attribute "{0}" value "{1}" not in {2} for aggregation {3}.'.format(
                        field, aggregation[field], field_data['values'], aggregation_idx
                    ))

    @staticmethod
    def validate_search_data(data_dict, user, search_position=None):
        search_position_str = ' for search {0}'.format(search_position) if search_position else ''

        try:
            dataset_id = data_dict['dataset']
        except:
            raise Exception('Mandatory "dataset" attribute is not defined{0}.'.format(search_position_str))

        try:
            dataset_id = int(dataset_id)
        except:
            raise Exception('"dataset" attribute{0} is not an integer.'.format(search_position_str))

        try:
            dataset = Dataset.objects.get(pk=dataset_id)
        except:
            raise Exception('No dataset ID matches the "dataset" attribute\'s value{0}.'.format(search_position_str))

        if not user.has_perm('permission_admin.can_access_dataset_%s' % dataset_id):
            raise Exception('No permission to query the dataset {0}{1}'.format(str(dataset_id), search_position_str))

        fields = data_dict.get('fields', [])

        if not isinstance(fields, list):
            raise Exception('"fields" attribute must be a list of strings{0}'.format(search_position_str))
        if not all(isinstance(field, str) for field in fields):
            raise Exception('"fields" attribute must be a list of strings{0}'.format(search_position_str))

        parameters = data_dict.get('parameters', {})
        if not isinstance(parameters, dict):
            raise Exception('"parameters" must be a dictionary{0}'.format(search_position_str))

        scroll = data_dict.get('scroll', False)
        if not isinstance(scroll, bool):
            raise Exception('"scroll" must be boolean{0}'.format(search_position_str))

        scroll_id = data_dict.get('scroll_id', u'')
        if not isinstance(scroll_id, str):
            raise Exception('"scroll_id" must be string{0}'.format(search_position_str))

        Validator._validate_constraints(data_dict.get('constraints', []), search_position)


    @staticmethod
    def _validate_constraints(constraints, search_position):
        for_search_position_str = ' for search {0}'.format(search_position) if search_position != None else ''
        in_search_position_str = ' in search {0}'.format(search_position) if search_position != None else ''

        if not isinstance(constraints, list):
            raise Exception('"constraints" must be a list of dictionaries{0}'.format(for_search_position_str))
        if not all(isinstance(constraint, dict) for constraint in constraints):
            raise Exception('"constraints" must be a list of dictionaries{0}'.format(for_search_position_str))

        for constraint_idx, constraint in enumerate(constraints):
            if 'class' not in constraint:
                raise Exception('"class" attribute missing for constraint {0}{1}.'.format(constraint_idx,
                                                                                          in_search_position_str))
            if constraint['class'] not in Validator.valid_fields:
                raise Exception('"class" attribute for constraint {0}{1} must have one of the following values: {2}'.format(
                    constraint_idx, in_search_position_str, [class_ for class_ in Validator.valid_fields]
                ))

            class_ = constraint['class']
            valid_constraint_fields = Validator.valid_fields[class_]

            for field in constraint:
                if field not in valid_constraint_fields:
                    raise Exception('"{0}" is not a valid attribute for constraint {1}{2}.'.format(
                        field, constraint_idx, in_search_position_str
                    ))

            for field in valid_constraint_fields:
                field_data = valid_constraint_fields[field]
                if field_data['mandatory'] and field not in constraint:
                    raise Exception('Constraint {0}{1} is missing mandatory attribute "{2}".'.format(
                        constraint_idx, in_search_position_str, field
                    ))
                if field_data['values'] and field in constraint and constraint[field] not in field_data['values']:
                    raise Exception('Attribute "{0}" value "{1}" not in {2} for constraint {3}{4}.'.format(
                        field, constraint[field], field_data['values'], constraint_idx, in_search_position_str
                    ))


    @staticmethod
    def get_validated_user(request):
        try:
            processed_query = json.loads(request.body)
        except:
            raise Exception('Unable to parse JSON.')

        try:
            auth_token = processed_query['auth_token']
        except:
            raise Exception('Authentication token missing.')

        try:
            profile = Profile.objects.get(auth_token = auth_token)
        except:
            raise Exception('Invalid authentication token.')

        return profile.user
