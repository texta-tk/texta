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
    unique name problem and testing it.
"""

def get_selected_fields(indices, fields):
    # get all fields in given indices
    all_fields = ElasticCore().get_fields(indices)
    # filter out selected fields
    selected_fields = [field for field in all_fields if field["path"] in fields]
    return selected_fields

def update_field_types(indices, fields, field_type):
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
    # obtain unique keys from parsed response
    keys = [field['type'] for field in my_fields]
    keys = list(set(keys))
    # create dicts for unique keys
    unique_dicts = [{key: []} for key in keys]
    # populate unique_dicts with their respective values
    for field in my_fields:
        for _dict in unique_dicts:
            if field['type'] in _dict.keys():
                my_key = field['type']
                _dict[my_key].append(field['path'])

    return unique_dicts


def update_mapping(schema_input, new_index):
    mod_schema = {"properties": {}}
    props = {}
    for schema in schema_input:
        prop = generate_mapping('a_mapping', schema)['mappings']['a_mapping']['properties']
        props.update(prop)
        mod_schema.update(properties=props)
    return {'mappings': {new_index: mod_schema}}


def generate_mapping(new_index, schema_input):
    return SchemaGenerator().generate_schema(new_index, schema_input)


def apply_elastic_search(elastic_search, fields):
    new_docs = []
    for document in elastic_search:
        new_doc = {k: v for k, v in document.items() if k in fields}
        if new_doc:
            new_docs.append(new_doc)
    return new_docs


def bulk_add_documents(elastic_search, fields, elastic_doc):
    new_docs = apply_elastic_search(elastic_search, fields)
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

    schema_input = update_field_types(indices, fields, field_type)
    updated_schema = update_mapping(schema_input, reindexer_obj.new_index)

    # create new_index
    create_index_res = ElasticCore().create_index(reindexer_obj.new_index, updated_schema)

    # set new_index name as mapping name, perhaps make it customizable in the future
    mapping_name = reindexer_obj.new_index
    bulk_add_documents(elastic_search, fields, elastic_doc)

    # get_map = ElasticCore().get_mapping(index=reindexer_obj.new_index)
    # print("ourmap", get_map)

    # declare the job done
    show_progress.update_step('')
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
