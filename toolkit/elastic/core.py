from elasticsearch import Elasticsearch
import urllib
import requests
from toolkit.settings import ES_URL

class ElasticCore:
    """
    Class for holding most general settings and Elasticsearch object itself
    """
    
    def __init__(self):
        self.es = Elasticsearch([ES_URL])
        self.connection = self._check_connection()
        self.TEXTA_RESERVED = ['texta_facts']


    def _check_connection(self):
        try:
            requests.get(ES_URL)
            return True
        except:
            return False


    @staticmethod
    def load_indices_from_field_data(field_data, indices):
        # try loading indices from field data. if not present, use list.
        if field_data:
            try:
                parsed_indices = list(set([field['index'] for field in field_data]))
                parsed_indices = ','.join(parsed_indices)
                return parsed_indices
            except:
                KeyError
        return indices


    def get_indices(self):
        if self.connection:
            return list(self.es.indices.get_alias('*').keys())
        else:
            return []


    def get_fields(self, indices=[]):
        out = []
        if indices:
            lookup = ','.join(indices)
        else:
            lookup = '*'
        if self.connection:
            for index, mappings in self.es.indices.get_mapping(lookup).items():
                for mapping, properties in mappings['mappings'].items():
                    properties = properties['properties']
                    for field in self._decode_mapping_structure(properties):
                        index_with_field = {'index': index, 'path': field['path'], 'type': field['type']}
                        out.append(index_with_field)
        return out
    

    def _decode_mapping_structure(self, structure, root_path=list(), nested_layers=list()):
        """
        Decode mapping structure (nested dictionary) to a flat structure
        """
        mapping_data = []
        for k,v in structure.items():
            # deal with fact field
            if 'properties' in v and k in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = [{'path': k, 'type': 'fact'}]
                mapping_data.extend(sub_mapping)
            # deal with object & nested structures 
            elif 'properties' in v and k not in self.TEXTA_RESERVED:
                sub_structure = v['properties']
                path_list = root_path[:]
                path_list.append(k)
                sub_mapping = self._decode_mapping_structure(sub_structure, root_path=path_list)
                mapping_data.extend(sub_mapping)
            else:
                path_list = root_path[:]
                path_list.append(k)
                path = '.'.join(path_list)
                data = {'path': path, 'type': v['type']}
                mapping_data.append(data)
        return mapping_data
