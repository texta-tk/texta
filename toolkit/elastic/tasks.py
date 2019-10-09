import json

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.elastic.models import Reindexer
from toolkit.base_task import BaseTask
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.document import ElasticDocument

""" TODOs:
    implement changing field types
    implement renaming fields: probably add to field_type new_field_name
    complete always, but give result message
    optimize show_progress
    implement query for advanced filtering.

"""

def update_field_types(indices, field_type):
    ''' if fieldtype, for field named fieldtype change its type'''
    my_fields = ElasticCore().get_fields(indices=indices)
    my_field_data = [field["path"] for field in my_fields]
    for field in field_type:
        if field['path'] in my_field_data:
            field_to_retype = field['path']
            new_type = field['field_type']
            for field in my_fields:
                if field['path'] == field_to_retype:
                    field['type'] = new_type
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

    # print(bool(field_type))

    if field_type:
        fields = update_field_types(indices, field_type)

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
