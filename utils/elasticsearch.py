import requests
from ..utils.es_manager import ES_Manager

def parse_mappings(datasets,es_url):
    mappings = {}
    i=0
    for dataset in datasets:
        dataset_mappings = ES_Manager.plain_get(es_url+'/'+dataset['name'])[dataset['name']]['mappings']
        for dataset_mapping in dataset_mappings:
            mappings[i] = {'date_range':dataset['date_range'],'dataset':dataset['name'],'mapping':dataset_mapping}
            i+=1
    return mappings
