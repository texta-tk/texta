from permission_admin.models import Dataset
import json

#TODO: make a proper class for dataset-related functions

def get_datasets():
    datasets = {}
    for dataset in Dataset.objects.all():
        datasets[dataset.pk] = {'date_range': json.loads(dataset.daterange),
                                'index': dataset.index,
                                'mapping': dataset.mapping}
    return datasets

def get_active_dataset(mapping_id):
    datasets = get_datasets()
    selected_mapping = int(mapping_id)
    dataset = datasets[selected_mapping]['index']
    mapping = datasets[selected_mapping]['mapping']
    date_range = datasets[selected_mapping]['date_range']
    return dataset,mapping,date_range
