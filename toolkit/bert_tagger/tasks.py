import json
import os
import secrets
import logging
from celery.decorators import task
from django.db import connections
from elasticsearch.helpers import streaming_bulk

from toolkit.core.task.models import Task

from toolkit.bert_tagger.models import BertTagger as BertTaggerObject
from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.data_sample import DataSample
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.document import ElasticDocument
from toolkit.tools.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, BERT_PRETRAINED_MODEL_DIRECTORY, BERT_FINETUNED_MODEL_DIRECTORY, BERT_CACHE_DIR, INFO_LOGGER, ERROR_LOGGER
from toolkit.helper_functions import get_core_setting, get_indices_from_object
from toolkit.bert_tagger import choices

from texta_bert_tagger.tagger import BertTagger

from typing import List, Union, Dict

@task(name="train_bert_tagger", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_bert_tagger(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = BertTaggerObject.objects.get(pk=tagger_id)
        task_object = tagger_object.task
        #model_type = BertTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)
        # get fields & indices
        fields = json.loads(tagger_object.fields)
        indices = get_indices_from_object(tagger_object)

        bert_model = tagger_object.bert_model

        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(
            tagger_object,
            indices,
            fields,
            show_progress=show_progress,
            join_fields=True
        )
        show_progress.update_step('training')
        show_progress.update_view(0.0)

        # select sklearn average function based on the number of classes
        if data_sample.is_binary:
            sklearn_avg_function = choices.DEFAULT_SKLEARN_AVG_BINARY
        else:
            sklearn_avg_function = choices.DEFAULT_SKLEARN_AVG_MULTICLASS


        # NB! saving pretrained models must be disabled!
        tagger = BertTagger(
            allow_standard_output = choices.DEFAULT_ALLOW_STANDARD_OUTPUT,
            autoadjust_batch_size = choices.DEFAULT_AUTOADJUST_BATCH_SIZE,
            sklearn_avg_function = sklearn_avg_function,
            use_gpu = choices.DEFAULT_USE_GPU,
            save_pretrained = False,
            pretrained_models_dir = "",
            logger = logging.getLogger(INFO_LOGGER),
            cache_dir = BERT_CACHE_DIR
        )

        # train tagger and get result statistics
        report = tagger.train(
            data_sample.data,
            n_epochs = tagger_object.num_epochs,
            max_length = tagger_object.max_length,
            batch_size = tagger_object.batch_size,
            lr = tagger_object.learning_rate,
            eps = tagger_object.eps,
            split_ratio = tagger_object.split_ratio,
            bert_model = bert_model
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
        # save tagger object
        tagger_object.save()
        # declare the job done
        task_object.complete()
        return True


    except Exception as e:
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise


def load_tagger(tagger_object: BertTaggerObject) -> BertTagger:
    """Load BERT tagger from disc."""

    # NB! Saving pretrained models must be disabled!
    tagger = BertTagger(
        allow_standard_output = choices.DEFAULT_ALLOW_STANDARD_OUTPUT,
        save_pretrained = False,
        use_gpu = choices.DEFAULT_USE_GPU,
        logger = logging.getLogger(INFO_LOGGER),
        cache_dir = BERT_CACHE_DIR
    )
    tagger.load(tagger_object.model.path)
    return tagger


def apply_loaded_tagger(tagger: BertTagger, tagger_object: BertTaggerObject, tagger_input: Union[str, Dict], input_type: str = "text", feedback: bool=False):
    """Apply loaded BERT tagger to doc or text."""
    # tag doc or text
    if input_type == 'doc':
        tagger_result = tagger.tag_doc(tagger_input)
    else:
        tagger_result = tagger.tag_text(tagger_input)

    # reform output
    prediction = {
        'probability': tagger_result['probability'],
        'tagger_id': tagger_object.id,
        'result': tagger_result['prediction']
    }
    # add optional feedback
    if feedback:
        project_pk = tagger_object.project.pk
        feedback_object = Feedback(project_pk, model_object=tagger_object)
        feedback_id = feedback_object.store(tagger_input, prediction['result'])
        feedback_url = f'/projects/{project_pk}/bert_taggers/{tagger_object.pk}/feedback/'
        prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}

    logging.getLogger(INFO_LOGGER).info(f"Prediction: {prediction}")
    return prediction


def apply_tagger(tagger_object: BertTaggerObject, tagger_input: Union[str, Dict], input_type: str='text', feedback: bool=False):
    """ Apply BERT tagger on a text or a document. Wraps functions load_tagger and apply_loaded_tagger."""

    # Load tagger
    tagger = load_tagger(tagger_object)

    # Predict with the loaded tagger
    prediction = apply_loaded_tagger(tagger, tagger_object, tagger_input, input_type, feedback)

    return prediction


def to_texta_facts(tagger_result: List[Dict[str, Union[str, int, bool]]], field: str, fact_name: str, fact_value: str):
    """ Format tagger predictions as texta facts."""
    if tagger_result["result"] == "false":
        return []

    new_fact = {
        "fact": fact_name,
        "str_val": fact_value,
        "doc_path": field,
        "spans": json.dumps([[0,0]])
    }
    logging.getLogger(INFO_LOGGER).info(f"Generated new fact: {new_fact}")

    return [new_fact]


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, fact_value: str, object: int, tagger: BertTagger = None):

    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling BERT Tagger with ID {object.id} to batch {i+1}...")
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            flat_hit = ec.flatten(hit)
            existing_facts = hit.get("texta_facts", [])

            for field in fields:
                text = flat_hit.get(field, None)
                if text and isinstance(text, str):

                    result = apply_loaded_tagger(tagger, object, text, input_type = "text", feedback = False)
                    #logging.getLogger(INFO_LOGGER).info(f"Result: {result}")

                    # If tagger is binary and fact value is not specified by the user, use tagger description as fact value
                    if result["result"] in ["true", "false"]:
                        if not fact_value:
                            fact_value = object.description

                    # For multitag, use the prediction as fact value
                    else:
                        fact_value = result["result"]


                    new_facts = to_texta_facts(result, field, fact_name, fact_value)
                    existing_facts.extend(new_facts)

            if existing_facts:
                # Remove duplicates to avoid adding the same facts with repetitive use.
                existing_facts = ElasticDocument.remove_duplicate_facts(existing_facts)

            hit["texta_facts"] = existing_facts

            yield {
                "_index": raw_doc["_index"],
                "_id": raw_doc["_id"],
                "_type": raw_doc.get("_type", "_doc"),
                "_op_type": "update",
                "_source": {'doc': hit},
            }


@task(name="apply_tagger_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_tagger_to_index(object_id: int, indices: List[str], fields: List[str], fact_name: str, fact_value: str, query: dict, bulk_size: int, max_chunk_bytes: int, es_timeout: int):
    try:
        max_retries = 3 # TODO: move somewhere
        object = BertTaggerObject.objects.get(pk=object_id)
        tagger = load_tagger(object)

        progress = ShowProgress(object.task)

        ec = ElasticCore()
        [ec.add_texta_facts_mapping(index) for index in indices]

        searcher = ElasticSearcher(
            indices = indices,
            field_data = fields + ["texta_facts"],  # Get facts to add upon existing ones.
            query = query,
            output = ElasticSearcher.OUT_RAW,
            timeout = f"{es_timeout}m",
            callback_progress=progress,
            scroll_size = bulk_size
        )

        actions = update_generator(generator=searcher, ec=ec, fields=fields, fact_name=fact_name, fact_value=fact_value, object=object, tagger=tagger)
        for success, info in streaming_bulk(client=ec.es, actions=actions, refresh="wait_for", chunk_size=bulk_size, max_chunk_bytes=max_chunk_bytes, max_retries=max_retries):
            if not success:
                logging.getLogger(ERROR_LOGGER).exception(json.dumps(info))

        object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        object.task.add_error(error_message)
