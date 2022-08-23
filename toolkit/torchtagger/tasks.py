import json
import logging
import os
import pathlib
import secrets
from typing import Dict, List, Union

from celery.decorators import task
from django.db import connections
from elasticsearch.helpers import streaming_bulk
from texta_elastic.core import ElasticCore
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher
from texta_embedding.embedding import W2VEmbedding
from texta_torch_tagger.tagger import TorchTagger

from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.tools.data_sample import DataSample
from toolkit.helper_functions import get_indices_from_object
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER, RELATIVE_MODELS_PATH
from toolkit.tools.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress
from toolkit.torchtagger.models import TorchTagger as TorchTaggerObject


@task(name="train_torchtagger", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_torchtagger(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = TorchTaggerObject.objects.get(pk=tagger_id)

        # Handle previous tagger models that exist in case of retrains.
        model_path = pathlib.Path(tagger_object.model.path) if tagger_object.model else None

        task_object = tagger_object.tasks.last()
        model_type = TorchTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)
        # get fields & indices
        fields = json.loads(tagger_object.fields)
        indices = get_indices_from_object(tagger_object)
        # load embedding
        embedding = W2VEmbedding()
        embedding.load_django(tagger_object.embedding)
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

        # get num examples and save to model
        num_examples = {k: len(v) for k, v in data_sample.data.items()}
        tagger_object.num_examples = json.dumps(num_examples)

        tagger_object.save()

        # create TorchTagger
        tagger = TorchTagger(
            embedding,
            model_arch=tagger_object.model_architecture
        )
        # train tagger and get result statistics
        report = tagger.train(data_sample.data, num_epochs=int(tagger_object.num_epochs), pos_label=tagger_object.pos_label)
        # close all db connections
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()
        # save tagger to disk
        tagger_path = os.path.join(RELATIVE_MODELS_PATH, model_type, f'{model_type}_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)

        # set tagger location
        tagger_object.model.name = tagger_path
        # save tagger plot
        report_dict = report.to_dict()
        tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_tagger_plot(report_dict), save=False)
        # save label index
        tagger_object.label_index = json.dumps(tagger.label_reverse_index)
        # stats to model object
        tagger_object.f1_score = report.f1_score
        tagger_object.precision = report.precision
        tagger_object.recall = report.recall
        tagger_object.accuracy = report.accuracy
        tagger_object.training_loss = report.training_loss
        tagger_object.epoch_reports = json.dumps([a.to_dict() for a in tagger.epoch_reports])
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


def apply_tagger(tagger_object: TorchTaggerObject, tagger_input: Union[str, Dict], input_type: str = 'text', feedback: bool = False):
    """Load tagger from the disc and predict with it. Wraps function load_tagger and apply_loaded_tagger."""
    # Load tagger
    tagger = tagger_object.load_tagger()
    # Predict with the loaded tagger
    prediction = tagger_object.apply_loaded_tagger(tagger, tagger_input, input_type, feedback)
    return prediction


def to_texta_facts(tagger_result: List[Dict[str, Union[str, int, bool]]], field: str, fact_name: str, fact_value: str, text: str):
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


def update_generator(generator: ElasticSearcher, ec: ElasticCore, fields: List[str], fact_name: str, fact_value: str, tagger_object: TorchTaggerObject, tagger: TorchTagger = None):
    for i, scroll_batch in enumerate(generator):
        logging.getLogger(INFO_LOGGER).info(f"Appyling Torch Tagger with ID {tagger_object.id} to batch {i + 1}...")
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

                    new_facts = to_texta_facts(result, field, fact_name, fact_value, text)
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


@task(name="apply_torch_tagger_to_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def apply_tagger_to_index(object_id: int, indices: List[str], fields: List[str], fact_name: str, fact_value: str, query: dict, bulk_size: int, max_chunk_bytes: int, es_timeout: int):
    """Apply Torch Tagger to index."""
    try:
        tagger_object = TorchTaggerObject.objects.get(pk=object_id)
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
