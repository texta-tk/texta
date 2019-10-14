import json

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.elastic.models import Reindexer
from toolkit.base_task import BaseTask
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.document import ElasticDocument
from toolkit.elastic.mapping_generator import SchemaGenerator

""" TODOs:
    complete always, but give result message
    optimize show_progress
    implement query for advanced filtering.
    unique name problem and testing it.
    bulk doc_add
"""

def update_field_types(indices, field_type):
    ''' if fieldtype, for field named fieldtype change its type'''
    # returns fields edited by serializer input
    my_fields = ElasticCore().get_fields(indices=indices)    # what if no indices
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
    # obtain unique keys from parsed response
    keys = []
    for field in my_fields:
        keys.append(field['type'])
    keys = list(set(keys))
    # create dicts for unique keys
    unique_dicts = []
    for key in keys:
        unique_dicts.append({key: []})
    # populate unique_dicts with their respective values
    for field in my_fields:
        for _dict in unique_dicts:
            if field['type'] in _dict.keys():
                my_key = field['type']
                _dict[my_key].append(field['path'])

    return unique_dicts


def generate_mapping(new_index, schema_input):
    return SchemaGenerator().generate_schema(new_index, schema_input)

def add_documents(elastic_search, fields, elastic_doc):
    # teha efektiivsemaks, bulk insert
    for document in elastic_search:
        new_doc = {k: v for k, v in document.items() if k in fields}
        if new_doc:
            elastic_doc.add(new_doc)

@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id, testing=False):
    reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
    task_object = reindexer_obj.task
    indices = json.loads(reindexer_obj.indices)
    fields = set(json.loads(reindexer_obj.fields))
    random_size = reindexer_obj.random_size
    field_type = json.loads(reindexer_obj.field_type.replace("'", '"'))

    ''' for empty field post, use all posted indices fields '''
    if fields == set():
        fields = ElasticCore().get_fields(indices=indices)
        fields = set(field["path"] for field in fields)

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    elastic_search = ElasticSearcher(indices=indices, callback_progress=show_progress)
    elastic_doc = ElasticDocument(reindexer_obj.new_index)

    if random_size > 0:
        elastic_search = ElasticSearcher(indices=indices).random_documents(size=random_size)

    ''' the operations that don't require mapping update have been completed '''

    if field_type:
        # create new mapping
        schema_input = update_field_types(indices, field_type)
        mod_schema = {"properties": {}}
        props = {}
        for schema in schema_input:
            prop = generate_mapping('a_mapping', schema)['mappings']['a_mapping']['properties']
            props.update(prop)
            mod_schema.update(properties=props)
        updated_schema = {'mappings': {reindexer_obj.new_index: mod_schema}}

        create_index_res = ElasticCore().create_index(reindexer_obj.new_index, updated_schema)
        print(create_index_res)

        # check new mapping ->
        # new_index_mapping = ElasticCore().get_mapping(reindexer_obj.new_index)
        # print(new_index_mapping)

    add_documents(elastic_search, fields, elastic_doc)

    # finish Task
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
