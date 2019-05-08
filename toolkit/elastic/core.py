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


    def get_indices(self):
        if self.connection:
            return list(self.es.indices.get_alias('*').keys())
        else:
            return []


    def get_fields(self):
        out = []
        if self.connection:
            for index, mappings in self.es.indices.get_mapping('*').items():
                for mapping, properties in mappings['mappings'].items():
                    properties = properties['properties']
                    for field in self._decode_mapping_structure(properties):
                        index_with_field = {'index': index, 'mapping': mapping, 'field': field}
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


    @staticmethod
    def encode_field_data(field):
        """
        Encodes field data into url (so it can be stored safely in Django data model)
        :result: urlencoded string
        """
        field_path = field['field']['path']
        field_type = field['field']['type']
        index = field['index']
        mapping = field['mapping']
        flat_field = {"index": index, "mapping": mapping, 
                    "field_path": field_path, "field_type": field_type}
        return urllib.parse.urlencode(flat_field)


    @staticmethod
    def decode_field_data(field):
        """
        Decodes urlencoded field data string into dict
        :result: field data in dict
        """
        parsed_dict = urllib.parse.parse_qs(urllib.parse.urlparse(field).path)
        parsed_dict = {a:b[0] for a,b in parsed_dict.items()}
        return parsed_dict


    @staticmethod
    def parse_field_data(field_data):
        """
        Parses field data list into dict with index names as keys and field paths as list of strings
        """
        parsed_data = {}
        for field in field_data:
            if field['index'] not in parsed_data:
                parsed_data[field['index']] = []
            parsed_data[field['index']].append(field['field_path'])
        return parsed_data
