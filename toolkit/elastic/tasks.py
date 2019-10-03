import json

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.elastic.models import Reindexer
from toolkit.base_task import BaseTask
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.document import ElasticDocument

"""Use cases:
        changing field names
        changing or adding types
        re-indexing: new or changed.

    An index is an optimized collection of documents;
    a document is a collection of document_fields;
    document_fields contain the key, value pairs that contain your data.

    TODOs:
    posting fields [] chooses all fields associated with our project index
    currently all fields are selected by default. from our project index, in the future should work with many indices.

    perhaps posting_fields should actually add fields to the new_index, makes more sense from a REST standpoint. If a filter is needed we can have filter_fields
    But really, we should do bulk filtering (subsets) and field-type changes through the QUERY.
    Posting indices into Reindexer always creates the same result; a reindexed index, of the count of new_index list and named by its elements.
    random subsetide oma implementeerida (olemas searchis)
"""

@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id, testing=False):
    reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
    task_object = reindexer_obj.task
    indices = json.loads(reindexer_obj.indices)
    fields = set(json.loads(reindexer_obj.fields))

    if fields == set():
        project_indices = reindexer_obj.project.indices
        project_fields = ElasticCore().get_fields(indices=project_indices)
        fields = [field["path"] for field in project_fields]

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    es_search = ElasticSearcher(indices=indices, callback_progress=show_progress)
    es_doc = ElasticDocument(reindexer_obj.new_index)
    for document in es_search:
        new_doc = {k:v for k,v in document.items() if k in fields}
        if new_doc:
            # add new document, contains a dict with {"posted_field_key", "posted_field_key_associated_values"}
            es_doc.add(new_doc)

    # finish Task
    # TODO, complete always, but give result message
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
