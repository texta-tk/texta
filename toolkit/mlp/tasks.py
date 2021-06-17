import json
import logging
from typing import List, Optional

from celery import group
from celery.decorators import task
from texta_mlp.mlp import MLP

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.tools.document import ESDocObject, ElasticDocument
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.mlp.helpers import process_lang_actions
from toolkit.mlp.models import ApplyLangWorker, MLPWorker
from toolkit.settings import (CELERY_LONG_TERM_TASK_QUEUE, CELERY_MLP_TASK_QUEUE, DEFAULT_MLP_LANGUAGE_CODES, ERROR_LOGGER, INFO_LOGGER, MLP_MODEL_DIRECTORY)
from toolkit.tools.show_progress import ShowProgress


# TODO Temporally as for now no other choice is found for sharing the models through the worker across the tasks.
mlp: Optional[MLP] = None


def load_mlp():
    global mlp
    if mlp is None:
        mlp = MLP(
            language_codes=DEFAULT_MLP_LANGUAGE_CODES,
            default_language_code="et",
            resource_dir=MLP_MODEL_DIRECTORY,
            logging_level="info"
        )


@task(name="apply_mlp_on_list", base=BaseTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_mlp_on_list(self, texts: List[str], analyzers: List[str]):
    load_mlp()
    response = []
    for text in texts:
        analyzed_text = mlp.process(text, analyzers)
        response.append(analyzed_text)
    return response


@task(name="apply_mlp_on_docs", base=BaseTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_mlp_on_docs(self, docs: List[dict], analyzers: List[str], fields_to_parse: List[str]):
    load_mlp()
    response = mlp.process_docs(docs=docs, analyzers=analyzers, doc_paths=fields_to_parse)
    return response


@task(name="apply_mlp_on_es_doc", base=TransactionAwareTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_mlp_on_es_doc(self, document_id, mlp_id):
    """
    Applies MLP on document retrieved from ES.
    Updates document in ES.
    """

    mlp_object = MLPWorker.objects.get(pk=mlp_id)
    task_object = mlp_object.task
    # Get the necessary fields.
    indices: List[str] = mlp_object.get_indices()
    # TODO: Check if this mechanism is valid
    indices_as_string = ",".join(indices)
    field_data: List[str] = json.loads(mlp_object.fields)
    analyzers: List[str] = json.loads(mlp_object.analyzers)
    try:
        load_mlp()
        # retrieve document from ES
        document = ESDocObject(document_id, indices_as_string)
        # apply MLP
        document.apply_mlp(mlp, analyzers, field_data)
        # send new doc to ES
        document.update()
        # update progress
        task_object.update_process_iteration(task_object.total, "MLP")
        logging.getLogger(INFO_LOGGER).info(f"Processed & updated document for MLP Task ID: {mlp_id}")
        return True
    except Exception as e:
        err_msg = f"{e}; Document ID: {document_id}"
        logging.getLogger(ERROR_LOGGER).exception(err_msg)
        task_object.add_error(err_msg)
        raise e


@task(name="start_mlp_worker", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_mlp_worker(self, mlp_id: int):
    """
    Scrolls the document ID-s and passes them to MLP worker.
    """
    logging.getLogger(INFO_LOGGER).info(f"Applying mlp on the index for MLP Task ID: {mlp_id}")
    mlp_object = MLPWorker.objects.get(pk=mlp_id)
    # init progress
    show_progress = ShowProgress(mlp_object.task, multiplier=1)
    show_progress.update_step('Scrolling document IDs')
    show_progress.update_view(0)
    # Get the necessary fields.
    indices: List[str] = mlp_object.get_indices()
    es_scroll_size = mlp_object.es_scroll_size
    es_timeout = mlp_object.es_timeout
    # create searcher object for scrolling ids
    searcher = ElasticSearcher(
        query=json.loads(mlp_object.query),
        indices=indices,
        output=ElasticSearcher.OUT_ID,
        callback_progress=show_progress,
        scroll_size=es_scroll_size,
        scroll_timeout=f"{es_timeout}m"
    )
    # add texta facts mappings to the indices if needed
    for index in indices:
        searcher.core.add_texta_facts_mapping(index=index)
    # list the id-s from generator
    doc_ids = list(searcher)
    # update progress
    show_progress.update_step(f'Applying MLP to {len(doc_ids)} documents')
    show_progress.update_view(0)
    # update total doc count
    task_object = mlp_object.task
    task_object.total = len(doc_ids)
    task_object.save()

    # pass document id-s to the next task
    chain = group(apply_mlp_on_es_doc.s(document_id=doc_id, mlp_id=mlp_id) for doc_id in doc_ids) | end_mlp_task.s()
    chain.delay()
    return True


@task(name="end_mlp_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def end_mlp_task(self, mlp_id):
    logging.getLogger(INFO_LOGGER).info(f"Finished applying mlp on the index for model ID: {mlp_id}")
    mlp_object = MLPWorker.objects.get(pk=mlp_id)
    mlp_object.task.complete()
    return True


@task(name="apply_lang_on_indices", base=TransactionAwareTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_lang_on_indices(self, apply_worker_id: int):
    worker_object = ApplyLangWorker.objects.get(pk=apply_worker_id)
    task_object = worker_object.task
    try:
        load_mlp()
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling through the indices to apply lang')

        # Get the necessary fields.
        indices: List[str] = worker_object.get_indices()
        field = worker_object.field

        scroll_size = 100
        searcher = ElasticSearcher(
            query=json.loads(worker_object.query),
            indices=indices,
            field_data=[field],
            output=ElasticSearcher.OUT_RAW,
            callback_progress=show_progress,
            scroll_size=scroll_size,
            scroll_timeout="15m"
        )

        for index in indices:
            searcher.core.add_texta_facts_mapping(index=index)

        actions = process_lang_actions(generator=searcher, field=field, worker_id=apply_worker_id, mlp_class=mlp)

        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)

        worker_object.task.complete()

        return apply_worker_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e
