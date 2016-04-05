from permission_admin.models import Dataset
import json

def get_datasets():
    datasets = {}
    for dataset in Dataset.objects.all():
        datasets[dataset.pk] = {'date_range': json.loads(dataset.daterange),
                                'index': dataset.index,
                                'mapping': dataset.mapping}
    return datasets
