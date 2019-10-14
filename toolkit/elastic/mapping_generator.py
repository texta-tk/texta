# -*- coding: utf-8 -*-


class SchemaGenerator:
    def __init__(self):
        pass

    def _get_text_structure(self):
        txt_structure = {"type": "text",
                         "fields": {
                             "keyword": {
                                 "type": "keyword",
                                 "ignore_above": 256
                             }
                         }}
        return txt_structure

    def _get_long_structure(self):
        long_structure = {"type": "long",
                          "fields": {
                              "keyword": {
                                  "type": "keyword",
                                  "ignore_above": 256
                              }
                          }}
        return long_structure

    def _get_date_structure(self):
        date_structure = {"type": "date"}
        return date_structure

    def _get_fact_structure(self):
        fact_structure = {"type": "nested",
                          "properties": {
                              "description": {
                                  "type": "text",
                                  "fields": {
                                      "keyword": {
                                          "type": "keyword",
                                          "ignore_above": 256
                                      }
                                  }
                              },
                              "doc_path": {
                                  "type": "keyword"
                              },
                              "fact": {
                                  "type": "keyword"
                              },
                              "num_val": {
                                  "type": "long"
                              },
                              "spans": {
                                  "type": "keyword"
                              },
                              "str_val": {
                                  "type": "keyword"
                              }
                          }}

        return fact_structure

    def get_nested_structure(self, nested_fields):
        nested = {}
        for field in nested_fields:
            tokens = field.split('.')
            for i, token in enumerate(tokens):
                if i == 0:
                    if token not in nested:
                        nested[token] = {'properties': {}}
                    nested_branch = nested
                elif i < len(tokens) - 1:
                    if token not in nested_branch[tokens[i - 1]]['properties']:
                        nested_branch[tokens[i - 1]]['properties'][token] = {'properties': {}}
                    nested_branch = nested_branch[tokens[i - 1]]['properties']
                else:
                    if token not in nested_branch[tokens[i - 1]]['properties']:
                        nested_branch[tokens[i - 1]]['properties'][token] = self._get_text_structure()
                    nested_branch = nested_branch[tokens[i - 1]]['properties']
        return nested

    def init_fields(self, fields):
        keys = ['text', 'date', 'long', 'nested', 'texta_facts']
        for key in keys:
            if key not in fields:
                fields.update({key: []})
        return fields

    def generate_schema(self, mapping_name, fields):
        '''
        fields: dict
        '''
        fields = self.init_fields(fields)
        schema = {'mappings': {mapping_name: {'properties': {}}}}
        text_structure = self._get_text_structure()
        long_structure = self._get_long_structure()
        date_structure = self._get_date_structure()
        fact_structure = self._get_fact_structure()

        for field in fields['text']:
            schema['mappings'][mapping_name]['properties'][field] = text_structure
        for field in fields['long']:
            schema['mappings'][mapping_name]['properties'][field] = long_structure
        for field in fields['date']:
            schema['mappings'][mapping_name]['properties'][field] = date_structure
        for field in fields['texta_facts']:
            schema['mappings'][mapping_name]['properties']['texta_facts'] = fact_structure
        if fields['nested']:
            nested_mapping = self.get_nested_structure(fields['nested'])
            schema['mappings'][mapping_name]['properties'].update(nested_mapping)

        return schema
