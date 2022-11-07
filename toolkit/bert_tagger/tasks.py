import json
import logging
import os
import pathlib
import secrets
from typing import Dict, List, Union

from celery.decorators import task
from django.conf import settings
from django.db import connections
from elasticsearch.helpers import streaming_bulk
from minio.error import MinioException
from texta_bert_tagger.tagger import BertTagger
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher

from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.bert_tagger import choices
from toolkit.bert_tagger.models import BertTagger as BertTaggerObject
from toolkit.core.task.models import Task
from toolkit.elastic.tools.data_sample import DataSample
from toolkit.helper_functions import get_indices_from_object
from toolkit.settings import BERT_CACHE_DIR, BERT_FINETUNED_MODEL_DIRECTORY, BERT_PRETRAINED_MODEL_DIRECTORY, CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER
from toolkit.tools.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress

# Global object for the worker so tagger models won't get reloaded on each task
# Essentially an indefinite cache
PERSISTENT_BERT_TAGGERS = {}


@task(name="apply_persistent_bert_tagger", base=BaseTask)
def apply_persistent_bert_tagger(tagger_input: Union[str, Dict], tagger_id: int, input_type: str = 'text', feedback: bool = False):
    """
    Task to use Bert models stored in memory for fast re-use.
    Stores models in dict.
    """
    global PERSISTENT_BERT_TAGGERS
    tagger_object = BertTaggerObject.objects.get(id=tagger_id)
    try:
        # load tagger object into cache if not there
        if tagger_id not in PERSISTENT_BERT_TAGGERS:
            PERSISTENT_BERT_TAGGERS[tagger_id] = tagger_object.load_tagger()
        # select loaded tagger from cache
        loaded_tagger = PERSISTENT_BERT_TAGGERS[tagger_id]
        return tagger_object.apply_loaded_tagger(loaded_tagger, tagger_input, input_type=input_type, feedback=feedback)
    except Exception as e:
        raise


@task(name="bert_download_tagger_model", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def download_tagger_model(minio_path: str, user_pk: int, project_pk: int, version_id: str):
    info_logger = logging.getLogger(settings.INFO_LOGGER)
    info_logger.info(f"[Bert Tagger] Starting to download model from Minio with path {minio_path}!")
    tagger_pk = BertTaggerObject.download_from_s3(minio_path, user_pk=user_pk, project_pk=project_pk, version_id=version_id)
    info_logger.info(f"[Bert Tagger] Finished to download model from Minio with path {minio_path}!")
    return tagger_pk


@task(name="bert_upload_tagger_files", base=TransactionAwareTask, queue=settings.CELERY_LONG_TERM_TASK_QUEUE)
def upload_tagger_files(tagger_id: int, minio_path: str):
    tagger = BertTaggerObject.objects.get(pk=tagger_id)
    task_object: Task = tagger.tasks.last()
    info_logger = logging.getLogger(settings.INFO_LOGGER)

    task_object.update_status(Task.STATUS_RUNNING)
    task_object.step = "uploading into S3"
    task_object.save()

    try:
        info_logger.info(f"[Bert Tagger] Starting to upload tagger with ID {tagger_id} into S3!")
        minio_path = minio_path if minio_path else tagger.generate_s3_location()
        data = tagger.export_resources()
        tagger.upload_into_s3(minio_path=minio_path, data=data)
        info_logger.info(f"[Bert Tagger] Finished upload of tagger with ID {tagger_id} into S3!")
        task_object.complete()

    except MinioException as e:
        task_object.handle_failed_task(f"Could not connect to S3, are you using the right credentials?")
        raise e

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e


@task(name="train_bert_tagger", base=TransactionAwareTask)
def train_bert_tagger(tagger_id, testing=False):
    # retrieve neurotagger & task objects
    tagger_object = BertTaggerObject.objects.get(pk=tagger_id)

    # Handle previous tagger models that exist in case of retrains.
    model_path = pathlib.Path(tagger_object.model.path) if tagger_object.model else None

    task_object = tagger_object.tasks.last()
    try:
        show_progress = ShowProgress(task_object, multiplier=1)
        # get fields & indices
        fields = json.loads(tagger_object.fields)
        indices = get_indices_from_object(tagger_object)

        # set loading model from a checkpoint False by default
        from_checkpoint = False
        checkpoint_model = tagger_object.checkpoint_model

        pos_label = tagger_object.pos_label

        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(
            tagger_object,
            indices,
            fields,
            show_progress=show_progress,
            join_fields=True,
            balance=tagger_object.balance,
            use_sentence_shuffle=tagger_object.use_sentence_shuffle,
            balance_to_max_limit=tagger_object.balance_to_max_limit
        )
        show_progress.update_step('training')
        show_progress.update_view(0.0)

        # select sklearn average function based on the number of classes
        if data_sample.is_binary:
            sklearn_avg_function = choices.DEFAULT_SKLEARN_AVG_BINARY
        else:
            sklearn_avg_function = choices.DEFAULT_SKLEARN_AVG_MULTICLASS

        # if checkpoint model is detected, load it and use it for further training
        if checkpoint_model:
            logging.getLogger(INFO_LOGGER).info(f"Loading model from a checkpoint stored in '{tagger_object}'...")

            # use the same pre-trained bert model as the checkpoint model
            tagger_object.bert_model = checkpoint_model.bert_model
            tagger = checkpoint_model.load_tagger()

            # set sklearn avg function in case the number of classes has changed
            tagger.sklearn_avg_function = sklearn_avg_function

            # set loading model from a checkpoint True
            from_checkpoint = True

        # if no checkpoint model is given, train a new model
        else:
            logging.getLogger(INFO_LOGGER).info("No checkpoint model detected, training a new model...")
            # NB! saving pretrained models must be disabled!
            tagger = BertTagger(
                allow_standard_output=choices.DEFAULT_ALLOW_STANDARD_OUTPUT,
                autoadjust_batch_size=choices.DEFAULT_AUTOADJUST_BATCH_SIZE,
                sklearn_avg_function=sklearn_avg_function,
                use_gpu=tagger_object.use_gpu,
                save_pretrained=False,
                pretrained_models_dir=BERT_PRETRAINED_MODEL_DIRECTORY,
                logger=logging.getLogger(INFO_LOGGER),
                cache_dir=BERT_CACHE_DIR
            )

        # use state dict for binary taggers
        if data_sample.is_binary:
            tagger.config.use_state_dict = True
        else:
            tagger.config.use_state_dict = False
            pos_label = ""

        # train tagger and get result statistics
        report = tagger.train(
            data_sample.data,
            from_checkpoint=from_checkpoint,
            pos_label=pos_label,
            n_epochs=tagger_object.num_epochs,
            max_length=tagger_object.max_length,
            batch_size=tagger_object.batch_size,
            lr=tagger_object.learning_rate,
            eps=tagger_object.eps,
            split_ratio=tagger_object.split_ratio,
            bert_model=tagger_object.bert_model
        )
        # close all db connections
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

        # save tagger to disc
        tagger_path = os.path.join(BERT_FINETUNED_MODEL_DIRECTORY, f'{tagger_object.MODEL_TYPE}_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)

        # set tagger location
        tagger_object.model.name = tagger_path

        report_dict = report.to_dict()

        # save tagger plot
        tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_tagger_plot(report_dict), save=False)
        # save label index
        tagger_object.label_index = json.dumps(tagger.config.label_reverse_index)
        # stats to model object
        tagger_object.f1_score = report.f1_score
        tagger_object.precision = report.precision
        tagger_object.recall = report.recall
        tagger_object.accuracy = report.accuracy
        tagger_object.training_loss = report.training_loss
        tagger_object.validation_loss = report.validation_loss
        tagger_object.epoch_reports = json.dumps([a.to_dict() for a in tagger.epoch_reports])
        tagger_object.num_examples = json.dumps({k: len(v) for k, v in list(data_sample.data.items())})
        tagger_object.adjusted_batch_size = tagger.config.batch_size
        tagger_object.confusion_matrix = json.dumps(report.confusion.tolist())
        tagger_object.classes = json.dumps(report.classes, ensure_ascii=False)
        # save tagger object
        tagger_object.save()
        # declare the job done
        task_object.complete()

        # Cleanup after the transaction to ensure integrity database records.
        if model_path and model_path.exists():
            model_path.unlink(missing_ok=True)

        return True


    except Exception as e:
        task_object.handle_failed_task(e)
        raise


def apply_tagger(tagger_object: BertTaggerObject, tagger_input: Union[str, Dict], input_type: str = 'text', feedback: bool = False):
    """ Apply BERT tagger on a text or a document. Wraps functions load_tagger and apply_loaded_tagger."""
    # Load tagger
    tagger = tagger_object.load_tagger()
    # Predict with the loaded tagger
    prediction = tagger_object.apply_loaded_tagger(tagger, tagger_input, input_type, feedback)
    return prediction


def to_texta_facts(tagger_result: List[Dict[str, Union[str, int, bool]]], field: str, fact_name: str, fact_value: str):
    """ Format tagger predictions as texta facts."""
    if tagger_result["result"] == "false":
        return []

    new_fact = {
        "fact": fact_name,
        "str_val": fact_value,
        "doc_path": field,
        "spans": json.dumps([[0, 0]]),
        "sent_index": 0
    }
    return [new_fact]


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, fact_value: str, tagger_object: BertTaggerObject, tagger: BertTagger = None):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling BERT Tagger with ID {tagger_object.id} to batch {i + 1}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):

                    result = tagger_object.apply_loaded_tagger(tagger, text, input_type="text", feedback=False)

                    # If tagger is binary and fact value is not specified by the user, use tagger description as fact value
                    if result["result"] in ["true", "false"]:
                        if not fact_value:
                            fact_value = tagger_object.description

                    # For multitag, use the prediction as fact value
                    else:
                        fact_value = result["result"]

                    new_facts = to_texta_facts(result, field, fact_name, fact_value)
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


@task(name="apply_bert_tagger_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_tagger_to_index(object_id: int, indices: List[str], fields: List[str], fact_name: str, fact_value: str, query: dict, bulk_size: int, max_chunk_bytes: int,
                          es_timeout: int):
    """Apply BERT Tagger to index."""
    try:
        tagger_object = BertTaggerObject.objects.get(pk=object_id)
        tagger = tagger_object.load_tagger()

        task_object = tagger_object.tasks.last()
        progress = ShowProgress(task_object)

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices=indices,
            field_data=fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query=query,
            output=ElasticSearcher.OUT_RAW,
            timeout=f"{es_timeout}m",
            callback_progress=progress,
            scroll_size=bulk_size
        )

        actions = update_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, fact_value=fact_value, tagger_object=tagger_object, tagger=tagger)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes, max_retries=3):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        task_object.complete()
        return True

    except Exception as e:
        task_object.handle_failed_task(e)
        raise e
