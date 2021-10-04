from celery.decorators import task
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
from toolkit.embedding.models import Embedding
from toolkit.tools.show_progress import ShowProgress
from toolkit.helper_functions import get_indices_from_object
from toolkit.tools.plots import create_tagger_plot

from toolkit.settings import (
    CELERY_LONG_TERM_TASK_QUEUE,
    #CELERY_MLP_TASK_QUEUE,
    #CELERY_SHORT_TERM_TASK_QUEUE,
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
        field = crf_object.field

        # load embedding if any
        #if crf_object.embedding:
        #    embedding = W2VEmbedding()
        #    embedding.load_django(tagger_object.embeˇdding)
        #else:
        #    embedding = None

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
        extractor = CRFExtractor(config = config)
        # train the CRF model
        model_full_path, relative_model_path = crf_object.generate_name("crf")
        report, _ = extractor.train(documents, save_path = model_full_path, mlp_field = field)
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
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="apply_crf_extractor", base=BaseTask)
def apply_crf_extractor(crf_id: int, mlp_document: dict):
    # Get CRF object
    crf_object = CRFExtractorObject.objects.get(pk=crf_id)
    # Load model from the disc
    crf_extractor = crf_object.load_extractor()
    # Use the loaded model for predicting
    prediction = crf_object.apply_loaded_extractor(crf_extractor, mlp_document)
    return prediction
