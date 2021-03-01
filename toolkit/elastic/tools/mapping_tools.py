from collections import defaultdict
from toolkit.elastic.tools.mapping_generator import SchemaGenerator
from toolkit.elastic.tools.core import ElasticCore


def get_selected_fields(indices, fields):
    # get all fields in given indices
    all_fields = ElasticCore().get_fields(indices)
    # filter out selected fields
    selected_fields = [field for field in all_fields if field["path"] in fields]
    return selected_fields


def add_nested(fields):
    for field in fields:
        if '.' in field['path']:
            field['type'] = 'nested'
    return fields


def reformat_for_schema_generator(fields, flatten_doc=False):
    if not flatten_doc:
        fields = add_nested(fields)
    formatted_fields = defaultdict(list)
    for field in fields:
        if field['path'] == 'texta_facts':
            formatted_fields['texta_facts'].append('texta_facts')
        else:
            formatted_fields[field['type']].append(field['path'])
    return dict(formatted_fields)


def update_field_types(indices, fields, field_type, flatten_doc=False):
    ''' if fieldtype, for field named fieldtype change its type'''

    # returns fields edited by serializer input
    my_fields = get_selected_fields(indices, fields)
    my_field_data = [field["path"] for field in my_fields]

    for item in field_type:
        if item['path'] in my_field_data:
            field_to_edit = item['path']
            new_type = item['field_type']

            for field in my_fields:
                if field['path'] == field_to_edit:
                    field['type'] = new_type
                    # TODO must work, also when only name is changed
                    if 'new_path_name' in item.keys():
                        new_path_name = item['new_path_name']
                        field['path'] = new_path_name
    updated_field_types = reformat_for_schema_generator(my_fields, flatten_doc)
    return updated_field_types


def update_mapping(schema_input, doc_type: str, add_facts_mapping):
    mod_schema = SchemaGenerator().generate_schema(schema_input, add_facts_mapping)
    return {'mappings': {"_doc": mod_schema}}
