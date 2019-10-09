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
    implement changing field types
    implement renaming fields: probably add to field_type new_field_name
    complete always, but give result message
    optimize show_progress
    implement query for advanced filtering.
"""

def update_field_types(indices, field_type, new_index):
    ''' if fieldtype, for field named fieldtype change its type'''
    my_fields = ElasticCore().get_fields(indices=indices)
    my_field_data = [field["path"] for field in my_fields]
    for field in field_type:
        if field['path'] in my_field_data:
            field_to_retype = field['path']
            new_type = field['field_type']

            if 'new_path_name' in field.keys():
                new_path_name = field['new_path_name']

            for field in my_fields:
                if field['path'] == field_to_retype:
                    field['type'] = new_type
                if 'new_path_name' in field.keys():
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

    schema_input = unique_dicts


    # field_list = [field["path"] for field in my_fields]

    # # we need a list of dictionaries, which contain the key of the mapping and the fields to be changed into that type
    # field_list = []
    # for element in field_type:
    #     if element['field_type'] == 'long':
    #         field_list.append(element['path'])
    # schema_input = {'long': field_list}

    # first arg is mapping_name
    generate_mapping = SchemaGenerator().generate_schema(new_index, schema_input[3])

    print(generate_mapping)
    # update mapping in core ->

    # return my_fields
    return [field["path"] for field in my_fields]

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

    if field_type:
        fields = update_field_types(indices, field_type, reindexer_obj.new_index)

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    elastic_search = ElasticSearcher(indices=indices, callback_progress=show_progress)
    elastic_doc = ElasticDocument(reindexer_obj.new_index)

    if random_size > 0:
        elastic_search = ElasticSearcher(indices=indices).random_documents(size=random_size)

    for document in elastic_search:
        new_doc = {k:v for k,v in document.items() if k in fields}
        if new_doc:
            elastic_doc.add(new_doc)

    # finish Task
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
