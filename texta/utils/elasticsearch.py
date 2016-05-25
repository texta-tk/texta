import requests

def parse_mappings(datasets,es_url):
    mappings = {}
    i=0
    for dataset in datasets:
        dataset_mappings = requests.get(es_url+'/'+dataset['name']).json()[dataset['name']]['mappings']
        for dataset_mapping in dataset_mappings:
            mappings[i] = {'date_range':dataset['date_range'],'dataset':dataset['name'],'mapping':dataset_mapping}
            i+=1
    return mappings
