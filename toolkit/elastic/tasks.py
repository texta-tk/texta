import json

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.elastic.models import Reindexer
from toolkit.base_task import BaseTask
from toolkit.tools.show_progress import ShowProgress
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.document import ElasticDocument


"""
    Create tasks here separately, for:
        changing field names
        changing or adding types
        re-indexing: new or changed.

    TODOs:
    Kas fieldid on olemas projektis, projekti mudelis on olemas meetod get_elastic_fields
    reindexer should add to project in format [first index count, ..., reindexed_index] because it is a set, unordered
    [] fields post valib kõik väljad
    random subsetide oma olemas searchis
    peaks ka käima juurde query, nagu embeddingus, selle abil saab valitud subsete teha.

"""

@task(name="reindex_task", base=BaseTask)
def reindex_task(reindexer_task_id, testing=False):
    # retrieve reindexer & task objects
    reindexer_obj = Reindexer.objects.get(pk=reindexer_task_id)
    task_object = reindexer_obj.task
    indices = json.loads(reindexer_obj.indices)
    fields = set(json.loads(reindexer_obj.fields))

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    es_search = ElasticSearcher(indices=indices, callback_progress=show_progress)
    es_doc = ElasticDocument(reindexer_obj.new_index)

    for document in es_search:
        # do stuff with the doc
        new_doc = {k:v for k,v in document.items() if k in fields}
        if new_doc:
            es_doc.add(new_doc)

    # finish Task
    # TODO, complete always, but give result message
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    return True
