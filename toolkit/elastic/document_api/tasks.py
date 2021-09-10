import json
import logging
from typing import List

from celery.decorators import task

from toolkit.base_tasks import QuietTransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.document_api.models import DeleteFactsByQueryTask, EditFactsByQueryTask
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.show_progress import ShowProgress


@task(name="start_fact_delete_query_task", base=QuietTransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_fact_delete_query_task(self, worker_id: int):
    """
    Scrolls the document ID-s and passes them to MLP worker.
    """
    worker_object = DeleteFactsByQueryTask.objects.get(pk=worker_id)
    logging.getLogger(INFO_LOGGER).info(f"Celery: Starting task for deleting facts by query for project with ID: {worker_object.pk}")

    # init progress
    show_progress = ShowProgress(worker_object.task, multiplier=1)
    show_progress.update_step('Scrolling document IDs')
    show_progress.update_view(0)

    # create searcher object for scrolling ids
    searcher = ElasticSearcher(
        query=json.loads(worker_object.query),
        indices=worker_object.get_indices(),
        output=ElasticSearcher.OUT_DOC,
        callback_progress=show_progress,
        scroll_size=worker_object.scroll_size,
        field_data=["texta_facts"]
    )

    count = searcher.count()
    show_progress.update_step(f'Deleting facts from {count} documents')
    show_progress.update_view(0)
    # update total doc count
    task_object = worker_object.task
    task_object.total = count
    task_object.save()

    return True


def query_delete_actions_generator(searcher, target_facts: List[dict]):
    for documents in searcher:
        for document in documents:
            source = document.get("_source")
            existing_facts = source.get("texta_facts", [])
            new_facts = []
            for index_count, existing_fact in enumerate(existing_facts):
                for fact in target_facts:
                    if not (fact.items() <= existing_fact.items()):
                        new_facts.append(existing_fact)

            document["_source"]["texta_facts"] = new_facts
            yield {
                "_op_type": "update",
                "_index": document["_index"],
                "_type": document.get("_type", "_doc"),
                "_id": document["_id"],
                "_source": {"doc": document["_source"]}
            }


@task(name="fact_delete_query_task", base=QuietTransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def fact_delete_query_task(self, worker_id: int):
    worker_object = DeleteFactsByQueryTask.objects.get(pk=worker_id)
    try:
        show_progress = ShowProgress(worker_object.task, multiplier=1)
        show_progress.update_step('Scrolling through the indices to delete the facts.')

        # Get the necessary fields.
        indices: List[str] = worker_object.get_indices()
        target_facts = json.loads(worker_object.facts)
        scroll_size = worker_object.scroll_size

        searcher = ElasticSearcher(
            query=json.loads(worker_object.query),
            indices=indices,
            field_data=["texta_facts"],
            output=ElasticSearcher.OUT_RAW,
            callback_progress=show_progress,
            scroll_size=scroll_size,
            scroll_timeout=f"{worker_object.es_timeout}m"
        )

        ed = ElasticDocument(index=None)
        actions = query_delete_actions_generator(searcher, target_facts)
        ed.bulk_update(actions)

        worker_object.task.complete()
        worker_object.save()

        return worker_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        worker_object.task.add_error(str(e))
        worker_object.task.update_status(Task.STATUS_FAILED)
        raise e


@task(name="start_fact_edit_query_task", base=QuietTransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_fact_edit_query_task(self, worker_id: int):
    """
    Scrolls the document ID-s and passes them to MLP worker.
    """
    worker_object = EditFactsByQueryTask.objects.get(pk=worker_id)
    logging.getLogger(INFO_LOGGER).info(f"Celery: Starting task for editing facts by query for project with ID: {worker_object.pk}")

    # init progress
    show_progress = ShowProgress(worker_object.task, multiplier=1)
    show_progress.update_step('Scrolling document IDs')
    show_progress.update_view(0)

    # create searcher object for scrolling ids
    searcher = ElasticSearcher(
        query=json.loads(worker_object.query),
        indices=worker_object.get_indices(),
        output=ElasticSearcher.OUT_DOC,
        callback_progress=show_progress,
        scroll_size=worker_object.scroll_size,
        field_data=["texta_facts"]
    )

    count = searcher.count()
    show_progress.update_step(f'Editing facts from {count} documents')
    show_progress.update_view(0)
    # update total doc count
    task_object = worker_object.task
    task_object.total = count
    task_object.save()

    return True


def query_edit_actions_generator(searcher, target_facts: List[dict], resulting_fact: dict):
    for documents in searcher:
        for document in documents:
            source = document.get("_source")
            existing_facts = source.get("texta_facts", [])
            for index_count, existing_fact in enumerate(existing_facts):
                for fact in target_facts:
                    if fact.items() <= existing_fact.items():
                        existing_facts[index_count] = resulting_fact

            document["_source"]["texta_facts"] = existing_facts
            yield {
                "_op_type": "update",
                "_index": document["_index"],
                "_type": document.get("_type", "_doc"),
                "_id": document["_id"],
                "_source": {"doc": document["_source"]}}


@task(name="fact_edit_query_task", base=QuietTransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def fact_edit_query_task(self, worker_id: int):
    worker_object = EditFactsByQueryTask.objects.get(pk=worker_id)
    try:
        show_progress = ShowProgress(worker_object.task, multiplier=1)
        show_progress.update_step('Scrolling through the indices to delete the facts.')

        # Get the necessary fields.
        indices: List[str] = worker_object.get_indices()
        target_facts = json.loads(worker_object.target_facts)
        fact = json.loads(worker_object.fact)
        scroll_size = worker_object.scroll_size

        searcher = ElasticSearcher(
            query=json.loads(worker_object.query),
            indices=indices,
            field_data=["texta_facts"],
            output=ElasticSearcher.OUT_RAW,
            callback_progress=show_progress,
            scroll_size=scroll_size,
            scroll_timeout=f"{worker_object.es_timeout}m"
        )

        ed = ElasticDocument(index=None)
        actions = query_edit_actions_generator(searcher, target_facts, resulting_fact=fact)
        ed.bulk_update(actions)

        worker_object.task.complete()
        worker_object.save()

        return worker_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        worker_object.task.add_error(str(e))
        worker_object.task.update_status(Task.STATUS_FAILED)
        raise e
