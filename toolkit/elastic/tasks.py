import json

from collections import defaultdict
from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.elastic.models import Reindexer
from toolkit.base_tasks import BaseTask
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.mapping_generator import SchemaGenerator

""" TODOs:
    unique name problem and testing it.
"""

# TODO: add this to reindex task params
FLATTEN_DOC = False

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

def update_mapping(schema_input, new_index):
    mod_schema = SchemaGenerator().generate_schema(schema_input)
    return {'mappings': {new_index: mod_schema}}

def unflatten_doc(doc):
    """ Unflatten document retrieved from ElasticSearcher.
    """
    unflattened_doc = {}
    nested_fields = [(k,v) for k, v in doc.items() if '.' in k]
    not_nested_fields = {k:v for k, v in doc.items() if '.' not in k}
    unflattened_doc.update(not_nested_fields)
    for k, v in nested_fields:
        layers = k.split('.')
        for i, layer in enumerate(layers):
            if i == 0:
                if layer not in unflattened_doc:
                    unflattened_doc[layer] = {}
                nested_branch = unflattened_doc
            elif i < len(layers)-1:
                if layer not in nested_branch[layers[i-1]]:
                    nested_branch[layers[i-1]][layer] = {}
                nested_branch = nested_branch[layers[i-1]]
            else:
                if layer not in nested_branch[layers[i-1]]:
                    nested_branch[layers[i-1]][layer] = v
                nested_branch = nested_branch[layers[i-1]]
    return unflattened_doc

def apply_elastic_search(elastic_search, fields, flatten_doc=False):
    new_docs = []
    for document in elastic_search:
        new_doc = {k: v for k, v in document.items() if k in fields}
        if not flatten_doc:
            new_doc = unflatten_doc(new_doc)
        if new_doc:
            new_docs.append(new_doc)
    return new_docs

def bulk_add_documents(elastic_search, fields, elastic_doc, flatten_doc=False):
    new_docs = apply_elastic_search(elastic_search, fields, flatten_doc)
    elastic_doc.bulk_add(new_docs)

@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id):
    reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
    task_object = reindexer_obj.task
    indices = json.loads(reindexer_obj.indices)
    fields = json.loads(reindexer_obj.fields)
    random_size = reindexer_obj.random_size
    field_type = json.loads(reindexer_obj.field_type)
    query = reindexer_obj.query

    ''' for empty field post, use all posted indices fields '''
    if not fields:
        fields = ElasticCore().get_fields(indices)
        fields = [field["path"] for field in fields]

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    elastic_search = ElasticSearcher(indices=indices, callback_progress=show_progress, query=query)
    elastic_doc = ElasticDocument(reindexer_obj.new_index)

    if random_size > 0:
        elastic_search = ElasticSearcher(indices=indices, query=query).random_documents(size=random_size)

    ''' the operations that don't require a mapping update have been completed '''

    schema_input = update_field_types(indices, fields, field_type, flatten_doc=FLATTEN_DOC)
    updated_schema = update_mapping(schema_input, reindexer_obj.new_index)

    # create new_index
    create_index_res = ElasticCore().create_index(reindexer_obj.new_index, updated_schema)

    # set new_index name as mapping name, perhaps make it customizable in the future
    mapping_name = reindexer_obj.new_index
    bulk_add_documents(elastic_search, fields, elastic_doc, flatten_doc=FLATTEN_DOC)

    # get_map = ElasticCore().get_mapping(index=reindexer_obj.new_index)
    # print("ourmap", get_map)

    # declare the job done
    task_object.complete()

    return True
