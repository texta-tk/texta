import json
from permission_admin.models import Dataset


class RestProcessor(object):

    @staticmethod
    def process(django_request):
        if django_request.method == 'GET':
            return RestProcessor._process_get(django_request)
        elif django_request.method == 'POST':
            return RestProcessor._process_post(django_request)

    @staticmethod
    def _process_get(django_request):
        dataset_id = int(django_request.GET['dataset'])
        dataset = Dataset.objects.get(pk=dataset_id)

        index = dataset.index
        mapping = dataset.mapping
        fields = django_request.GET.get('fields', "[]")
        constraints = django_request.GET.get('constraints', "[]")
        parameters = django_request.GET.get('parameters', "[]")

        return {
            'dataset': dataset_id,
            'index': index,
            'mapping': mapping,
            'fields': json.loads(fields),
            'constraints': json.loads(constraints),
            'parameters': json.loads(parameters)
        }

    @staticmethod
    def _process_post(django_request):
        processed_query = json.loads(django_request.body)

        dataset_id = int(processed_query['dataset'])
        dataset = Dataset.objects.get(pk=dataset_id)

        for key in ['fields', 'constraints', 'parameters']:
            if key not in processed_query:
                processed_query[key] = []

        processed_query['dataset'] = dataset_id
        processed_query['index'] = dataset.index
        processed_query['mapping'] = dataset.mapping

        return processed_query