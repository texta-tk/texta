import json
import logging
from typing import List, Optional

from celery.decorators import task
from texta_mlp.mlp import MLP

from toolkit.core.task.models import Task
from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.elastic.tools.document import ElasticDocument, ESDoc
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.mlp.helpers import process_lang_actions, process_mlp_actions
from toolkit.mlp.models import ApplyLangWorker, MLPWorker
from toolkit.settings import (
    CELERY_MLP_TASK_QUEUE,
    CELERY_LONG_TERM_TASK_QUEUE,
    DEFAULT_MLP_LANGUAGE_CODES,
    INFO_LOGGER,
    ERROR_LOGGER,
    MLP_MODEL_DIRECTORY
)
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




@task(name="start_mlp_worker", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_mlp_worker(self, mlp_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting applying mlp on the index for model ID: {mlp_id}")
    mlp_object = MLPWorker.objects.get(pk=mlp_id)

    show_progress = ShowProgress(mlp_object.task, multiplier=1)
    show_progress.update_step('Scrolling document IDs')
    show_progress.update_view(0)

    # Get the necessary fields.
    indices: List[str] = mlp_object.get_indices()
    analyzers: List[str] = json.loads(mlp_object.analyzers)

    # create searcher object for scrolling ids
    scroll_size = 100
    searcher = ElasticSearcher(
            query=json.loads(mlp_object.query),
            indices=indices,
            output=ElasticSearcher.OUT_ID,
            callback_progress=show_progress,
            scroll_size=scroll_size,
            scroll_timeout="30m"
    )

    for index in indices:
        searcher.core.add_texta_facts_mapping(index=index)

    docs = list(searcher)

    show_progress.update_step(f'Applying MLP to {len(docs)} documents')
    show_progress.update_view(0)

    task_object = mlp_object.task
    task_object.total = len(docs)
    task_object.save()

    return docs


@task(name="apply_mlp_on_es_doc", base=TransactionAwareTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_mlp_on_es_doc(self, document_id: str, mlp_id: int):
    mlp_object = MLPWorker.objects.get(pk=mlp_id)
    task_object = mlp_object.task
    
    indices: List[str] = mlp_object.get_indices()
    indices_as_string = ",".join(indices)
    field_data: List[str] = json.loads(mlp_object.fields)
    analyzers: List[str] = json.loads(mlp_object.analyzers)

    try:
        load_mlp()
        
        document = ESDoc(document_id)
        document.apply_mlp(mlp, analyzers, field_data)
        document.update()
        
        print("done")
        
        task_object.update_process_iteration(task_object.total, "MLP")

        return None

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        #task_object.add_error(str(e))
        #task_object.update_status(Task.STATUS_FAILED)
        raise e


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
