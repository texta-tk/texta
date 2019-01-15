import requests
from typing import *


class DashboardEsHelper:

    def __init__(self, es_url, indices):
        self.es_url = es_url
        self.indices = indices

    def get_mapping_schema(self) -> dict:
        """
        Using the _mapping endpoint of Elasticsearch, returns the mapping dictionary
        of all the indices specified. Supports multi-index.
        :return: Mappings of the doc_types.
        """
        endpoint_url = '{0}/{1}/_mapping'.format(self.es_url, self.indices)
        response = requests.get(endpoint_url)
        return response.json()

    def get_field_mappings(self) -> dict:
        """
        Uses the _mapping endpoint to fetch the mapping data of ALL the fields in
        the specified indices. This includes Elasticsearch's built-in values like "_id" and "_source".
        :return:
        """
        url_endpoint = "{0}/{1}/_mapping/*/field/*".format(self.es_url, self.indices)
        response = requests.get(url_endpoint).json()

        return response

    def add_is_nested_to_fields(self, nested_fields, fields_and_types: List[Dict], field_name_key='full_path'):
        """
        Given a list of dictionaries where the keys are field names,
        adds a value that determines if that field is of the nested datatype.
        :param nested_fields:
        :param field_name_key: Key name that contains the field name.
        :param fields_and_types: List of dictionaries that contain an ES field names (including dot notation)
        :return:
        """
        new_list = []

        for field_dict in fields_and_types:
            for nested_field_name in nested_fields:
                if nested_field_name in field_dict[field_name_key]:
                    field_dict['is_nested'] = True
                else:
                    field_dict['is_nested'] = False
                new_list.append(field_dict)

        return new_list

    def get_nested_field_names(self):
        """
        Traverses the doc_type's mapping schema to return
        a list with unique field names of fields that are of the nested datatype.
        Supports multiple indices.
        :return:
        """
        index_mapping = self.get_mapping_schema()
        nested_field_names = []

        for index_name, index_dict in index_mapping.items():
            for mapping_name, mapping_dict in index_dict['mappings'].items():
                for field_name, field_dict in mapping_dict['properties'].items():
                    if field_dict.get('type', None) == "nested":
                        nested_field_names.append(field_name)

        without_duplicates = list(set(nested_field_names))
        return without_duplicates

    def get_field_types(self, filtered_field_mapping) -> List[Dict[str, str]]:
        """
        Parses the results of the _mapping endpoint for fields to extract only the
        full path name of the field and its type. Nested fields are not included,
        multi-fields are by dot notation.
        :return:
        """
        all_fields = []

        for field_name, field_dict in filtered_field_mapping.items():
            if field_dict['mapping']:  # Empty dicts evaluate to False.
                full_path_and_types = dict()
                mapping_key = list(field_dict['mapping'].keys())[0]

                full_path_and_types['full_path'] = field_dict['full_name']
                full_path_and_types['type'] = field_dict['mapping'][mapping_key]['type']
                all_fields.append(full_path_and_types)

        return all_fields

    def get_filtered_field_mappings(self, es_field_mappings: dict) -> dict:
        """
        Given the results of the _mapping endpoint for fields,
        removes all keys that contains built-in ES values.
        :return:
        """
        elastic_keys = ["_seq_no", "_mapping", "_id", "_version", "_uid", "_type", "_source", "_field_names", "_all", "_index", "_parent", "_routing"]
        filtered_dict = dict()

        for index_name, index_dict in es_field_mappings.items():
            for mapping_name, mappings_dict in index_dict['mappings'].items():
                for field_name, field_dict in mappings_dict.items():
                    if field_name not in elastic_keys:
                        filtered_dict[field_name] = field_dict

        return filtered_dict

    def split_nested_fields(self, fields_and_types: List[Dict]):
        nested_fields = []
        normal_fields = []

        for field in fields_and_types:
            if field.get('is_nested', None) is True:
                nested_fields.append(field)
            elif field.get('is_nested', None) is False:
                normal_fields.append(field)

        return normal_fields, nested_fields

    def get_aggregation_field_data(self):
        """
        Implements the helper functions to give the necessary data
        about fields which is needed for the aggregations.
        :return:
        """
        names_of_nested_fields = self.get_nested_field_names()

        field_mappings = self.get_field_mappings()
        filtered_field_mappings = self.get_filtered_field_mappings(field_mappings)
        fieldnames_and_types = self.get_field_types(filtered_field_mappings)
        with_is_nested = self.add_is_nested_to_fields(names_of_nested_fields, fieldnames_and_types)

        normal_fields, nested_fields = self.split_nested_fields(with_is_nested)

        for nested_field in nested_fields:
            nested_field['parent'] = nested_field['full_path'].split('.')[0]  # By ES dot notation, "field.data"

        return normal_fields, nested_fields
