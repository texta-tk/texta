import json
from permission_admin.models import Dataset


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
        dataset_id = int(django_request.GET['dataset'])
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
        processed_query = json.loads(django_request.body)

        dataset_id = int(processed_query['dataset'])
        dataset = Dataset.objects.get(pk=dataset_id)

        for key in ['fields', 'constraints', 'parameters']:
            if key not in processed_query:
                processed_query[key] = []

        processed_query['dataset'] = dataset_id
        processed_query['index'] = dataset.index
        processed_query['mapping'] = dataset.mapping
        processed_query['scroll'] = True if 'scroll' in processed_query and processed_query['scroll'].lower() == 'true' else False

        return processed_query

    @staticmethod
    def _process_aggregator_get(django_request):
        pass

    @staticmethod
    def _process_aggregator_post(django_request):
        processed_query = json.loads(django_request.body)

        for search in processed_query['searches']:
            dataset_id = int(search['dataset'])
            dataset = Dataset.objects.get(pk=dataset_id)

            for key in ['fields', 'constraints', 'parameters']:
                if key not in search:
                    search[key] = []

            search['dataset'] = dataset_id
            search['index'] = dataset.index
            search['mapping'] = dataset.mapping

        return processed_query