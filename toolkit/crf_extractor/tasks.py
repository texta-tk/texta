from celery.decorators import task
from typing import List
import pathlib
import logging
import secrets
import json
import os

from texta_crf_extractor.crf_extractor import CRFExtractor

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from texta_elastic.searcher import ElasticSearcher
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
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
from .models import CRFExtractor as CRFExtractorObject


@task(name="start_crf_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def start_crf_task(crf_id: int):
    """
    Starts the training process for Extractor.
    """
    extractor = CRFExtractorObject.objects.get(pk=crf_id)
    task_object = extractor.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting tagging')
    show_progress.set_progress()
    return crf_id


@task(name="train_crf_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_crf_task(crf_id: int):
    """
    Trains CRF model.
    """
    try:
        # get task object
        logging.getLogger(INFO_LOGGER).info(f"Starting task 'train_crf' for CRFExtractor with ID: {crf_id}!")
        crf_object = CRFExtractorObject.objects.get(id=crf_id)
        task_object = crf_object.task
        # create progress object
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling documents')
        show_progress.set_progress()
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
            query=crf_object.get_query(),
            indices=indices,
            callback_progress=show_progress,
            text_processor=None,
            field_data=[mlp_field, "texta_facts"],
            output=ElasticSearcher.OUT_DOC,
            flatten=False
        )

        # create config
        config = crf_object.get_crf_config()
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
            "best_c_values": extractor.best_c_values,
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
        crf_object = CRFExtractorObject.objects.get(pk=crf_id)
        task_object = crf_object.task
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="save_crf_results", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def save_crf_results(result_data: dict):
    """
    Saves task results to database.
    """
    try:
        crf_id = result_data['id']
        logging.getLogger(INFO_LOGGER).info(f"Starting task results for CRFExtractor with ID: {crf_id}!")
        crf_object = CRFExtractorObject.objects.get(pk=crf_id)
        task_object = crf_object.task
        show_progress = ShowProgress(task_object, multiplier=1)
        # update status to saving
        show_progress.update_step('saving')
        show_progress.set_progress()
        crf_object.best_c1 = result_data["best_c_values"][0]
        crf_object.best_c2 = result_data["best_c_values"][1]
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
    """
    Applies Extractor to mlp document.
    """
    # Get CRF object
    crf_object = CRFExtractorObject.objects.get(pk=crf_id)
    # Load model from the disc
    crf_extractor = crf_object.load_extractor()
    # Use the loaded model for predicting
    prediction = crf_object.apply_loaded_extractor(crf_extractor, mlp_document)
    return prediction


def update_generator(
    generator: ElasticSearcher,
    ec: ElasticCore,
    mlp_fields: List[str],
    label_suffix: str,
    object_id: int,
    extractor: CRFExtractor = None
    ):
    """
    Tags & updates documents in ES.
    """
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling CRFExtractor with ID {object_id} to batch {i + 1}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            existing_facts = hit.get("texta_facts", [])
            for mlp_field in mlp_fields:
                new_facts = extractor.tag(hit, field_name=mlp_field, label_suffix=label_suffix)["texta_facts"]
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
def apply_crf_extractor_to_index(
    object_id: int,
    indices: List[str],
    mlp_fields: List[str],
    label_suffix: str,
    query: dict,
    bulk_size: int,
    max_chunk_bytes: int,
    es_timeout: int
    ):
    """
    Applies Extractor to ES index.
    """
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
        actions = update_generator(
            generator=searcher,
            ec=ec,
            mlp_fields=mlp_fields,
            label_suffix=label_suffix,
            object_id=object_id,
            extractor=extractor
        )
        # perform updates
        try:
            # as we have defined indices in actions there is no need to do it again (None)
            ElasticDocument(None).bulk_update(actions)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
        # all done
        crf_object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."
        crf_object = CRFExtractorObject.objects.get(pk=object_id)
        crf_object.task.add_error(error_message)
        crf_object.task.update_status(Task.STATUS_FAILED)
