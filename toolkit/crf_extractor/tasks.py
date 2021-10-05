from celery.decorators import task
from elasticsearch.helpers import streaming_bulk
from typing import List
import pathlib
import logging
import secrets
import json
import os

from texta_crf_extractor.crf_extractor import CRFExtractor
from texta_crf_extractor.config import CRFConfig

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from .models import CRFExtractor as CRFExtractorObject
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.embedding.models import Embedding
from toolkit.tools.show_progress import ShowProgress
from toolkit.helper_functions import get_indices_from_object
from toolkit.tools.plots import create_tagger_plot

from toolkit.settings import (
    CELERY_LONG_TERM_TASK_QUEUE,
    CELERY_SHORT_TERM_TASK_QUEUE,
    ERROR_LOGGER,
    INFO_LOGGER,
    MEDIA_URL
)


@task(name="start_crf_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def start_crf_task(crf_id: int):
    extractor = CRFExtractorObject.objects.get(pk=crf_id)
    task_object = extractor.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting tagging')
    show_progress.update_view(0)
    return crf_id


@task(name="train_crf_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_crf_task(crf_id: int):
    try:
        # get task object
        logging.getLogger(INFO_LOGGER).info(f"Starting task 'train_crf' for CRFExtractor with ID: {crf_id}!")
        crf_object = CRFExtractorObject.objects.get(id=crf_id)
        task_object = crf_object.task
        # create progress object
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling documents')
        show_progress.update_view(0)
        # retrieve indices & field data
        indices = get_indices_from_object(crf_object)
        mlp_field = crf_object.mlp_field

        # load embedding if any
        if crf_object.embedding:
            embedding = crf_object.embedding.get_embedding()
            embedding.load_django(crf_object.embedding)
        else:
            embedding = None

        # scroll docs
        logging.getLogger(INFO_LOGGER).info(f"Scrolling data for CRFExtractor with ID: {crf_id}!")
        documents = ElasticSearcher(
            query=json.loads(crf_object.query),
            indices=indices,
            callback_progress=show_progress,
            text_processor=None,
            output=ElasticSearcher.OUT_DOC,
            flatten=False
        )
        # create config
        config = CRFConfig(
            labels = json.loads(crf_object.labels),
            num_iter = crf_object.num_iter,
            test_size = crf_object.test_size,
            c1 = crf_object.c1,
            c2 = crf_object.c2,
            bias = crf_object.bias,
            window_size = crf_object.window_size,
            suffix_len = tuple(json.loads(crf_object.suffix_len)),
            context_feature_layers = crf_object.context_feature_fields,
            context_feature_extractors = crf_object.context_feature_extractors,
            feature_layers = crf_object.feature_fields,
            feature_extractors = crf_object.feature_extractors
        )
        # start training
        logging.getLogger(INFO_LOGGER).info(f"Training the model for CRFExtractor with ID: {crf_id}!")
        # create extractor
        extractor = CRFExtractor(config=config, embedding=embedding)
        # train the CRF model
        model_full_path, relative_model_path = crf_object.generate_name("crf")
        report, _ = extractor.train(documents, save_path = model_full_path, mlp_field = mlp_field)
        # Save the image before its path.
        image_name = f'{secrets.token_hex(15)}.png'
        crf_object.plot.save(image_name, create_tagger_plot(report.to_dict()), save=False)
        image_path = pathlib.Path(MEDIA_URL) / image_name
        # pass results to next task
        return {
            "id": crf_id,
            "extractor_path": relative_model_path,
            "precision": float(report.precision),
            "recall": float(report.recall),
            "f1_score": float(report.f1_score),
            "confusion_matrix": report.confusion.tolist(),
            "model_size": round(float(os.path.getsize(model_full_path)) / 1000000, 1),  # bytes to mb
            "plot": str(image_path),
        }


    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="save_crf_results", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def save_crf_results(result_data: dict):
    try:
        crf_id = result_data['id']
        logging.getLogger(INFO_LOGGER).info(f"Starting task results for CRFExtractor with ID: {crf_id}!")
        crf_object = CRFExtractorObject.objects.get(pk=crf_id)
        task_object = crf_object.task
        show_progress = ShowProgress(task_object, multiplier=1)
        # update status to saving
        show_progress.update_step('saving')
        show_progress.update_view(0)
        crf_object.model.name = result_data["extractor_path"]
        crf_object.precision = result_data["precision"]
        crf_object.recall = result_data["recall"]
        crf_object.f1_score = result_data["f1_score"]
        crf_object.model_size = result_data["model_size"]
        crf_object.confusion_matrix = result_data["confusion_matrix"]
        crf_object.plot.name = result_data["plot"]
        crf_object.save()
        task_object.complete()
        return True
    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        crf_object = CRFExtractorObject.objects.get(pk=crf_id)
        task_object = crf_object.task
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="apply_crf_extractor", base=BaseTask, QUEUE=CELERY_SHORT_TERM_TASK_QUEUE)
def apply_crf_extractor(crf_id: int, mlp_document: dict):
    # Get CRF object
    crf_object = CRFExtractorObject.objects.get(pk=crf_id)
    # Load model from the disc
    crf_extractor = crf_object.load_extractor()
    # Use the loaded model for predicting
    prediction = crf_object.apply_loaded_extractor(crf_extractor, mlp_document)
    return prediction


def to_texta_fact(results: List[dict], field: str):
    new_facts = []
    for result in results:
        for fact_name, fact_value in result.items():
            new_fact = {
                "fact": fact_name,
                "str_val": fact_value,
                "doc_path": field + "text",
                # need to get real spans!!
                "spans": json.dumps([[0, 0]])
            }
            new_facts.append(new_fact)
    return new_facts


def update_generator(generator: ElasticSearcher, ec: ElasticCore, mlp_fields: List[str], object_id: int, extractor: CRFExtractor = None):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling CRFExtractor with ID {object_id} to batch {i + 1}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            existing_facts = hit.get("texta_facts", [])

            for mlp_field in mlp_fields:
                result = extractor.tag(hit, field_name=mlp_field)

                # do this in package instead!!!
                new_facts = to_texta_fact(result, mlp_field)

                if new_facts:
                    existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "_source": {"doc": {"texta_facts": existing_facts}}
            }


@task(name="apply_crf_extractor_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_crf_extractor_to_index(object_id: int, indices: List[str], mlp_fields: List[str], query: dict, bulk_size: int, max_chunk_bytes: int, es_timeout: int):
    try:
        # load model
        crf_object = CRFExtractorObject.objects.get(pk=object_id)
        extractor = crf_object.load_extractor()
        # progress
        progress = ShowProgress(crf_object.task)
        # add fact field if missing
        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]
        # search
        searcher = ElasticSearcher(
            indices=indices,
            field_data=mlp_fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=query,
            output=ElasticSearcher.OUT_RAW,
            timeout=f"{es_timeout}m",
            callback_progress=progress,
        )
        # create update actions
        actions = update_generator(generator=searcher, ec=ec, mlp_fields=mlp_fields, object_id=object_id, extractor=extractor)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes, max_retries=3):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))
        # all done
        crf_object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        crf_object = CRFExtractorObject.objects.get(pk=object_id)
        crf_object.task.add_error(error_message)
        crf_object.task.update_status(Task.STATUS_FAILED)