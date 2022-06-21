import json
import os
import secrets
import logging
import pathlib

import math
import numpy as np

from celery.decorators import task
from copy import deepcopy
from django.db import connections

from toolkit.base_tasks import TransactionAwareTask
from toolkit.core.task.models import Task

from texta_elastic.searcher import ElasticSearcher
from texta_elastic.aggregator import ElasticAggregator

from toolkit.evaluator.models import Evaluator
from toolkit.evaluator import choices
from toolkit.evaluator.helpers.entity_evaluator import scroll_and_score_entity
from toolkit.evaluator.helpers.binary_and_multilabel_evaluator import (
    scroll_and_score,
    delete_empty_rows_and_cols,
    is_enough_memory_available,
    get_memory_imprint,
    remove_not_found
)

from toolkit.helper_functions import get_core_setting, calculate_memory_buffer

from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, INFO_LOGGER, ERROR_LOGGER, MEDIA_URL, EVALUATOR_MEMORY_BUFFER_RATIO

from toolkit.tools.show_progress import ShowProgress
from toolkit.tools.plots import create_confusion_plot

from typing import List, Union, Dict, Tuple


@task(name="evaluate_entity_tags", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def evaluate_entity_tags_task(object_id: int, indices: List[str], query: dict, es_timeout: int = 10, scroll_size: int = 100):
    try:
        logging.getLogger(INFO_LOGGER).info(f"Starting entity evaluator task for Evaluator with ID {object_id}.")

        evaluator_object = Evaluator.objects.get(pk=object_id)
        progress = ShowProgress(evaluator_object.task, multiplier=1)

        true_fact = evaluator_object.true_fact
        pred_fact = evaluator_object.predicted_fact

        add_misclassified_examples = evaluator_object.add_misclassified_examples
        token_based = evaluator_object.token_based

        # If the user hasn't defined a field, retrieve it automatically
        if not evaluator_object.field:
            es_aggregator = ElasticAggregator(indices=indices, query=deepcopy(query))
            true_fact_doc_paths = es_aggregator.facts_abstract(key_field="fact", value_field="doc_path", filter_by_key=true_fact)
            doc_path = true_fact_doc_paths[0]
        else:
            doc_path = evaluator_object.field

        searcher = ElasticSearcher(
            indices = indices,
            field_data = [doc_path, "texta_facts"],
            query = query,
            output = ElasticSearcher.OUT_RAW,
            timeout = f"{es_timeout}m",
            callback_progress=progress,
            scroll_size = scroll_size
        )

        # Get number of documents
        n_docs = searcher.count()
        evaluator_object.task.total = n_docs
        evaluator_object.task.save()

        evaluator_object.document_count = n_docs
        evaluator_object.scores_imprecise = False
        evaluator_object.score_after_scroll = False
        evaluator_object.add_individual_results = False

        # Save model updates
        evaluator_object.save()

        # Get number of batches for the logger
        n_batches = math.ceil(n_docs/scroll_size)

        scores, misclassified = scroll_and_score_entity(searcher, evaluator_object, true_fact, pred_fact, doc_path, token_based, n_batches, add_misclassified_examples)


        logging.getLogger(INFO_LOGGER).info(f"Final scores: {scores}")

        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()


        # Generate confusion matrix plot and save it
        image_name = f"{secrets.token_hex(15)}.png"
        classes = ["other", true_fact]
        evaluator_object.plot.save(image_name, create_confusion_plot(scores["confusion_matrix"], classes), save=False)
        image_path = pathlib.Path(MEDIA_URL) / image_name
        evaluator_object.plot.name = str(image_path)

        evaluator_object.save()
        evaluator_object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        evaluator_object.task.add_error(error_message)
        evaluator_object.task.update_status(Task.STATUS_FAILED)


@task(name="evaluate_tags", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def evaluate_tags_task(object_id: int, indices: List[str], query: dict, es_timeout: int = 10, scroll_size: int = 100):
    try:
        logging.getLogger(INFO_LOGGER).info(f"Starting evaluator task for Evaluator with ID {object_id}.")

        evaluator_object = Evaluator.objects.get(pk=object_id)
        progress = ShowProgress(evaluator_object.task, multiplier=1)

        # Retreieve facts and sklearn average function from the model
        true_fact = evaluator_object.true_fact
        pred_fact = evaluator_object.predicted_fact
        true_fact_value = evaluator_object.true_fact_value
        pred_fact_value = evaluator_object.predicted_fact_value

        average = evaluator_object.average_function
        add_individual_results = evaluator_object.add_individual_results

        searcher = ElasticSearcher(
            indices = indices,
            field_data = ["texta_facts"],
            query = query,
            output = ElasticSearcher.OUT_RAW,
            timeout = f"{es_timeout}m",
            callback_progress=progress,
            scroll_size = scroll_size
        )

        # Binary
        if true_fact_value and pred_fact_value:
            logging.getLogger(INFO_LOGGER).info(f"Starting binary evaluation. Comparing following fact and fact value pairs: TRUE: ({true_fact}: {true_fact_value}), PREDICTED: ({pred_fact}: {pred_fact_value}).")

            # Set the evaluation type in the model
            evaluator_object.evaluation_type = "binary"

            true_set = {true_fact_value, "other"}
            pred_set = {pred_fact_value, "other"}

            classes = ["other", true_fact_value]
            n_total_classes = len(classes)

        # Multilabel/multiclass
        else:
            logging.getLogger(INFO_LOGGER).info(f"Starting multilabel evaluation. Comparing facts TRUE: '{true_fact}', PRED: '{pred_fact}'.")

            # Make deepcopy of the query to avoid modifying Searcher's query.
            es_aggregator = ElasticAggregator(indices=indices, query=deepcopy(query))

            # Get all fact values corresponding to true and predicted facts to construct total set of labels
            # needed for confusion matrix, individual score calculations and memory imprint calculations
            true_fact_values = es_aggregator.facts(size=choices.DEFAULT_MAX_AGGREGATION_SIZE, filter_by_fact_name=true_fact)
            pred_fact_values = es_aggregator.facts(size=choices.DEFAULT_MAX_AGGREGATION_SIZE, filter_by_fact_name=pred_fact)

            true_set = set(true_fact_values)
            pred_set = set(pred_fact_values)

            classes = list(true_set.union(pred_set))
            n_total_classes = len(classes)

            # Add dummy classes for missing labels
            classes.extend([choices.MISSING_TRUE_LABEL, choices.MISSING_PRED_LABEL])


            ## Set the evaluation type in the model
            evaluator_object.evaluation_type = "multilabel"

            classes.sort(key=lambda x: x[0].lower())

        # Get number of documents in the query to estimate memory imprint
        n_docs = searcher.count()
        evaluator_object.task.total = n_docs
        evaluator_object.task.save()

        logging.getLogger(INFO_LOGGER).info(f"Number of documents: {n_docs} | Number of classes: {len(classes)}")

        # Get the memory buffer value from core variables
        core_memory_buffer_value_gb = get_core_setting("TEXTA_EVALUATOR_MEMORY_BUFFER_GB")

        # Calculate the value based on given ratio if the core variable is empty
        memory_buffer_gb = calculate_memory_buffer(memory_buffer=core_memory_buffer_value_gb, ratio=EVALUATOR_MEMORY_BUFFER_RATIO, unit="gb")

        required_memory = get_memory_imprint(n_docs=n_docs, n_classes=len(classes), eval_type=evaluator_object.evaluation_type, unit="gb", int_size=64)
        enough_memory = is_enough_memory_available(required_memory=required_memory, memory_buffer=memory_buffer_gb, unit="gb")

        # Enable scoring after each scroll if there isn't enough memory
        # for calculating the scores for the whole set of documents at once.
        score_after_scroll = False if enough_memory else True

        # If scoring after each scroll is enabled and scores are averaged after each scroll
        # the results for each averaging function besides `micro` are imprecise
        scores_imprecise = True if (score_after_scroll and average != "micro") else False

        # Store document counts, labels' class counts and indicatior if scores are imprecise
        evaluator_object.document_count = n_docs
        evaluator_object.n_true_classes = len(true_set)
        evaluator_object.n_predicted_classes = len(pred_set)
        evaluator_object.n_total_classes = n_total_classes
        evaluator_object.scores_imprecise = scores_imprecise
        evaluator_object.score_after_scroll = score_after_scroll

        # Save model updates
        evaluator_object.save()

        logging.getLogger(INFO_LOGGER).info(f"Enough available memory: {enough_memory} | Score after scroll: {score_after_scroll}")

        # Get number of batches for the logger
        n_batches = math.ceil(n_docs/scroll_size)

        # Scroll and score tags
        scores, bin_scores = scroll_and_score(generator=searcher, evaluator_object=evaluator_object, true_fact = true_fact, pred_fact = pred_fact, true_fact_value = true_fact_value, pred_fact_value=pred_fact_value, classes=classes, average=average, score_after_scroll=score_after_scroll, n_batches=n_batches, add_individual_results=add_individual_results)

        logging.getLogger(INFO_LOGGER).info(f"Final scores: {scores}")

        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

        confusion = scores["confusion_matrix"]
        confusion = np.asarray(confusion, dtype="int64")

        if len(classes) <=  choices.DEFAULT_MAX_CONFUSION_CLASSES:
            # Delete empty rows and columns corresponding to missing pred/true labels from the confusion matrix
            confusion, classes = delete_empty_rows_and_cols(confusion, classes)

        scores["confusion_matrix"] = confusion.tolist()

        # Generate confusion matrix plot and save it
        image_name = f"{secrets.token_hex(15)}.png"
        evaluator_object.plot.save(image_name, create_confusion_plot(scores["confusion_matrix"], classes), save=False)
        image_path = pathlib.Path(MEDIA_URL) / image_name
        evaluator_object.plot.name = str(image_path)

        # Add final scores to the model
        evaluator_object.precision = scores["precision"]
        evaluator_object.recall = scores["recall"]
        evaluator_object.f1_score = scores["f1_score"]
        evaluator_object.accuracy = scores["accuracy"]
        evaluator_object.confusion_matrix = json.dumps(scores["confusion_matrix"])

        evaluator_object.individual_results = json.dumps(remove_not_found(bin_scores), ensure_ascii=False)
        evaluator_object.add_misclassified_examples = False


        evaluator_object.save()
        evaluator_object.task.complete()
        return True

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        error_message = f"{str(e)[:100]}..."  # Take first 100 characters in case the error message is massive.
        evaluator_object.task.add_error(error_message)
        evaluator_object.task.update_status(Task.STATUS_FAILED)
