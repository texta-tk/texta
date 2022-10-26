import json
import logging
from typing import List, Optional

from celery import group
from celery.decorators import task
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from texta_mlp.mlp import MLP

from toolkit.base_tasks import BaseTask, QuietTransactionAwareTask, TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.helper_functions import chunks_iter
from toolkit.mlp.helpers import process_lang_actions
from toolkit.mlp.models import ApplyLangWorker, MLPWorker
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_MLP_TASK_QUEUE, DEFAULT_MLP_LANGUAGE_CODES, ERROR_LOGGER, INFO_LOGGER, MLP_BATCH_SIZE, MLP_GPU_DEVICE_ID, \
    MLP_MODEL_DIRECTORY, MLP_USE_GPU, TEXTA_TAGS_KEY, MLP_DEFAULT_LANGUAGE
from toolkit.tools.show_progress import ShowProgress


# TODO Temporally as for now no other choice is found for sharing the models through the worker across the tasks.
mlp: Optional[MLP] = None


def load_mlp():
    global mlp
    if mlp is None:
        mlp = MLP(
            language_codes=DEFAULT_MLP_LANGUAGE_CODES,
            default_language_code=MLP_DEFAULT_LANGUAGE,
            resource_dir=MLP_MODEL_DIRECTORY,
            logging_level="info",
            use_gpu=MLP_USE_GPU,
            gpu_device_id=MLP_GPU_DEVICE_ID
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


def get_mlp_object(mlp_id: int):
    """
    This will fail when pulling a MLP task object which doesn't
    exist anymore, like when the users wants to cancel the task.
    :param mlp_id: Primary Key of the MLPWorker database table.
    :return: ORM of the MLPWorker object.
    """
    mlp_object = MLPWorker.objects.get(pk=mlp_id)
    return mlp_object


def apply_mlp_on_documents(documents: List[dict], analyzers: List[str], field_data: List[str], mlp_id: int):
    # Apply MLP
    try:
        load_mlp()
        spans = "sentence" if "sentences" in analyzers or "all" in analyzers else "text"
        documents = mlp.process_docs(documents, analyzers=analyzers, doc_paths=field_data, spans=spans)
        return documents

    except Exception as e:
        # In case MLP fails, add error to document
        worker: MLPWorker = MLPWorker.objects.get(pk=mlp_id)
        worker.tasks.last().handle_failed_task(e)
        return documents


def update_documents_in_es(documents: List[dict]):
    """
    Updates the documents inside Elasticsearch, either with the MLP results or the
    error messages.

    :param documents: Full Elasticsearch documents..
    """
    ed = ElasticDocument(index=None)
    ed.bulk_update(actions=documents)


def unite_source_with_meta(meta_docs, source_docs):
    container = []
    for index, document in enumerate(source_docs):
        document = {**meta_docs[index], "_op_type": "update", "doc": document}
        del document["_source"]
        container.append(document)
    return container


@task(name="apply_mlp_on_es_doc", base=QuietTransactionAwareTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_mlp_on_es_docs(self, source_and_meta_docs: List[str], mlp_id: int):
    """
    Applies MLP on documents received by previous tasks and updates them in Elasticsearch.
    :param self: Reference to the Celery Task object of this task, courtesy of the bind parameter in the decorator.
    :param source_and_meta_docs: List of Elasticsearch document ID's to pull from Elasticsearch.
    :param mlp_id: ID of the MLPObject which contains progress.
    """
    mlp_object = get_mlp_object(mlp_id)

    task_object = mlp_object.tasks.last()

    # Get the necessary fields.
    field_data: List[str] = json.loads(mlp_object.fields)
    if TEXTA_TAGS_KEY not in field_data:
        # Add in existing facts so that proper duplicate filtering would be applied.
        field_data.append(TEXTA_TAGS_KEY)

    analyzers: List[str] = json.loads(mlp_object.analyzers)

    # retrieve document from ES
    document_wrapper = ElasticDocument(index=None)
    source_and_meta_docs = document_wrapper.get_bulk(doc_ids=source_and_meta_docs, fields=field_data)

    source_documents = [doc["_source"] for doc in source_and_meta_docs]
    mlp_docs = apply_mlp_on_documents(source_documents, analyzers, field_data, mlp_id)
    es_documents = unite_source_with_meta(source_and_meta_docs, mlp_docs)
    update_documents_in_es(es_documents)

    # Update progress
    task_object.update_progress_iter(len(source_and_meta_docs))
    return True


@task(name="start_mlp_worker", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_mlp_worker(self, mlp_id: int):
    """
    Scrolls the document ID-s and passes them to MLP worker.
    """
    mlp_object = MLPWorker.objects.get(pk=mlp_id)

    task_object = mlp_object.tasks.last()
    try:
        logging.getLogger(INFO_LOGGER).info(f"Applying mlp on the index for MLP Task ID: {mlp_id}")
        # init progress
        show_progress = ShowProgress(task_object, multiplier=1)
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
            output=ElasticSearcher.OUT_META,
            callback_progress=show_progress,
            scroll_size=es_scroll_size,
            scroll_timeout=f"{es_timeout}m"
        )
        # add texta facts mappings to the indices if needed
        for index in indices:
            searcher.core.add_texta_facts_mapping(index=index)

        doc_chunks = list(chunks_iter(searcher, MLP_BATCH_SIZE))

        # update progress
        show_progress.update_step(f'Applying MLP to {len(doc_chunks)} documents')
        show_progress.update_view(0)

        task_object.set_total(searcher.count())
        task_object.update_status(Task.STATUS_RUNNING)

        # pass document id-s to the next task
        chain = group(apply_mlp_on_es_docs.s([doc["_id"] for doc in meta_chunk], mlp_id) for meta_chunk in doc_chunks) | end_mlp_task.si(mlp_id)
        chain.delay()
        return True

    except Exception as e:
        task_object.handle_failed_task(e)
        raise


@task(name="end_mlp_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def end_mlp_task(self, mlp_id):
    logging.getLogger(INFO_LOGGER).info(f"Finished applying mlp on the index for model ID: {mlp_id}")
    mlp_object = MLPWorker.objects.get(pk=mlp_id)
    mlp_object.tasks.last().complete()
    return True


@task(name="apply_lang_on_indices", base=TransactionAwareTask, queue=CELERY_MLP_TASK_QUEUE, bind=True)
def apply_lang_on_indices(self, apply_worker_id: int):
    worker_object = ApplyLangWorker.objects.get(pk=apply_worker_id)
    task_object = worker_object.tasks.last()
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

        worker_object.tasks.last().complete()

        return apply_worker_id

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e
