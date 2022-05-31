
import numpy as np
import json
import psutil
import logging
from collections import defaultdict
from typing import List, Union, Tuple, Dict
from texta_elastic.searcher import ElasticSearcher

from toolkit.evaluator.models import Evaluator
from toolkit.evaluator import choices

from sklearn.metrics import precision_score, recall_score, accuracy_score, f1_score, confusion_matrix
from sklearn.preprocessing import MultiLabelBinarizer

from toolkit.settings import INFO_LOGGER


def are_empty_rows_and_cols(array: np.array, indx: int):
    """ Checks if the row and column at index `indx` in 2-dimensional array are consisting of zeros."""
    if not array[indx,:].any() and not array[:,indx].any():
        return True
    return False


def delete_empty_cols(true_labels: np.array, pred_labels: np.array, classes: List[Union[str, int]]) -> Tuple[np.array, np.array]:
    """ Deletes empty columns corresponding to missing pred/true labels from true and predicted label arrays."""
    if choices.MISSING_PRED_LABEL in classes and choices.MISSING_TRUE_LABEL in classes:
        missing_pred_label_indx = classes.index(choices.MISSING_PRED_LABEL)
        missing_true_label_indx = classes.index(choices.MISSING_TRUE_LABEL)
        indices = [missing_pred_label_indx, missing_true_label_indx]
        indices_to_del = []

        for indx in indices:
            if not true_labels[:, indx].any() and not pred_labels[:, indx].any():
                indices_to_del.append(indx)
        if indices_to_del:
            # Delete empty cols
            true_labels = np.delete(true_labels, indices_to_del, axis=1)
            pred_labels = np.delete(pred_labels, indices_to_del, axis=1)

    return (true_labels, pred_labels)


def delete_empty_rows_and_cols(confusion: np.array, classes: List[Union[str, int]]) -> Tuple[np.array, List[Union[str, int]]]:
    """ Deletes empty columns and rows corresponding to missing pred/true labels from a confusion matrix."""
    if choices.MISSING_PRED_LABEL in classes and choices.MISSING_TRUE_LABEL in classes:
        missing_pred_label_indx = classes.index(choices.MISSING_PRED_LABEL)
        missing_true_label_indx = classes.index(choices.MISSING_TRUE_LABEL)

        indices_to_del = []
        if are_empty_rows_and_cols(confusion, missing_pred_label_indx):
            indices_to_del.append(missing_pred_label_indx)
            classes = [c for c in classes if c != choices.MISSING_PRED_LABEL]

        if are_empty_rows_and_cols(confusion, missing_true_label_indx):
            indices_to_del.append(missing_true_label_indx)
            classes = [c for c in classes if c != choices.MISSING_TRUE_LABEL]

        # Delete empty rows
        confusion = np.delete(confusion, indices_to_del, axis=0)

        # Delete empty cols
        confusion = np.delete(confusion, indices_to_del, axis=1)
    return (confusion, classes)


def remove_not_found(binary_results: dict) -> dict:
    """ Removes labels not present in the data (necessary for removing missing true and pred labels, if they don't exist)"""
    cleaned_results = {}
    for label, label_scores in list(binary_results.items()):
        for metric in ["precision", "recall", "f1_score"]:
            if label_scores[metric] > -1:
                cleaned_results[label] = label_scores
                break
    return cleaned_results


def filter_results(binary_results: dict, min_count: int, max_count: int, metric_restrictions: dict) -> dict:
    """ Filter multilabel scores based on label count and metric scores restrictions. """
    filtered_scores = {}

    for label, label_scores in list(binary_results.items()):
        cm = np.array(label_scores["confusion_matrix"])
        fns = cm[0][0]

        # Remove false negative from the confusion matrix to
        # get the total count of labels
        count = np.sum(cm) - fns

        if min_count <= count <= max_count:

            # Add label count to the output
            label_scores["count"] = count

            filters_passed = True
            # Check if the label scores pass all restrictions
            for metric, restrictions in list(metric_restrictions.items()):
                if ("min_score" in restrictions and label_scores[metric] < restrictions["min_score"]) or \
                   ("max_score" in restrictions and label_scores[metric] > restrictions["max_score"]):
                   filters_passed = False
                   break

            if filters_passed:
                filtered_scores[label] = label_scores
    return filtered_scores


def filter_and_average_results(binary_results: dict, min_count: int, max_count: int, metric_restrictions: dict) -> dict:
    """ Calculate average of filtered tag scores. """
    metrics = choices.METRICS
    filtered_scores = {metric: [] for metric in metrics}

    for label, label_scores in list(binary_results.items()):
        cm = np.array(label_scores["confusion_matrix"])
        fns = cm[0][0]

        # Remove false negative from the confusion matrix to
        # get the total count of labels
        count = np.sum(cm) - fns

        # If label count is in required range, add scores to corresponding lists
        if min_count <= count <= max_count:
            filters_passed = True

            # Check if the label scores pass all restrictions
            for metric, restrictions in list(metric_restrictions.items()):
                if ("min_score" in restrictions and label_scores[metric] < restrictions["min_score"]) or \
                   ("max_score" in restrictions and label_scores[metric] > restrictions["max_score"]):
                   filters_passed = False
                   break

            if filters_passed:
                for metric in metrics:
                    filtered_scores[metric].append(label_scores[metric])

    # Calculate average scores of filtered scores
    avg_scores = {}
    for metric in metrics:
        if filtered_scores[metric]:
            avg_scores[metric] = np.mean(filtered_scores[metric])
        else:
            avg_scores[metric] = 0
    avg_scores["count"] = len(filtered_scores[metric])
    return avg_scores


def get_memory_imprint(n_docs: int, n_classes: int, eval_type: str, unit="gb", int_size: int=64) -> int:
    """ Get required memory space for 2 matrices with size (n_docs, n_classes)
    and dtype = int{int_size}.
    """
    unit_map = {"gb": 1024**3, "mb": 1024**2, "kb": 1024**1, "b": 1024**0}

    # Memory imprint for sparse label matrices
    matrices_imprint = 2*((n_docs*n_classes*(int_size/(2**3)))/unit_map[unit])

    # Memory imprint for list of all classes
    classes_list_imprint = (n_classes*(int_size/(2**3)))/unit_map[unit]

    if eval_type == "binary":
        total_imprint = matrices_imprint + classes_list_imprint

    else:
        # For mutlilabel and multiclass evaluation, individial scores are stored as well
        binary_results_imprint = 2*((n_docs*(int_size/(2**3)))/unit_map[unit])
        total_imprint = matrices_imprint + classes_list_imprint + binary_results_imprint

    return total_imprint


def is_enough_memory_available(required_memory: float, memory_buffer: float, unit="gb") -> bool:
    """ Checks if the system has enough memory for the task."""

    unit_map = {"gb": 1024**3, "mb": 1024**2, "kb": 1024**1, "b": 1024**0}

    available_memory = max(0, (psutil.virtual_memory().available / unit_map[unit]) - memory_buffer)

    logging.getLogger(INFO_LOGGER).info(f"Required memory: {round(required_memory, 2)}{unit.upper()} | Memory buffer: {memory_buffer}{unit.upper()} | Available memory: {round(available_memory, 2)}{unit.upper()}")
    return available_memory >= required_memory


def get_facts_by_name(texta_facts: List[dict], fact_name: str):
    """ Returns list of fact values corresponding to `fact_name`. """
    return [fact["str_val"] for fact in texta_facts if fact["fact"] == fact_name]


def get_scores(true_labels: List[Union[str, int]], pred_labels: List[Union[str, int]], classes: List[str], average: str, add_individual_results: bool) -> dict:
    """ Calculate different metrics' scores with sklearn. """

    bin_scores = {}

    # Multilabel and multiclass
    if len(classes) > 2:
        # Binarize multilabel results
        mlb = MultiLabelBinarizer(classes=classes)

        true_labels = mlb.fit_transform(true_labels).astype("int8")
        pred_labels = mlb.fit_transform(pred_labels).astype("int8")

        confusion_classes = [i for i in range(len(classes))]

        if len(classes) <= choices.DEFAULT_MAX_CONFUSION_CLASSES:
            confusion = confusion_matrix(true_labels.argmax(axis=1), pred_labels.argmax(axis=1), labels=confusion_classes)
        else:
            confusion = np.array([[]])

        # Calculate scores for each individual label as well
        if add_individual_results:
            for i, label_class in enumerate(classes):
                label_scores = get_scores(true_labels[:, i], pred_labels[:, i], classes=[0, 1], average="binary", add_individual_results=add_individual_results)
                label_scores.pop("bin_scores")
                bin_scores[label_class] = label_scores
    # Binary
    else:
        # Use numerical classes for binary taggers to avoid conflicts
        # when calculating confusion matrix
        classes = [0, 1]
        confusion = confusion_matrix(true_labels, pred_labels, labels=classes)

    # Convert the labels to numpy array for the usage of np.any()
    true_labels = np.array(true_labels)
    pred_labels = np.array(pred_labels)

    # Delete empty columns corresponding to missing true/pred labels
    true_labels, pred_labels = delete_empty_cols(true_labels, pred_labels, classes)

    # If bot true labels and pred labels contain only zeoros,
    # add nan marker as a marker to ignore these scores while calculating averages
    if not true_labels.any() and not pred_labels.any():
        precision = choices.SCORES_NAN_MARKER
        recall = choices.SCORES_NAN_MARKER
        f1 = choices.SCORES_NAN_MARKER
    else:
        precision = precision_score(true_labels, pred_labels, average=average)
        recall = recall_score(true_labels, pred_labels, average=average)
        f1 = f1_score(true_labels, pred_labels, average=average)

    # It's OK for accuracy if the label arrays contain only zeros
    accuracy = accuracy_score(true_labels, pred_labels)

    scores = {
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "accuracy": accuracy,
        "confusion_matrix": confusion,
        "bin_scores": bin_scores
    }
    return scores


def update_scores(scores_buffer: dict, batch_scores: dict) -> dict:
    """
    Update scores in `score_buffer` with scores in `batch_scores`.
    Return updated buffer.
    """

    # Convert confusion matrix from list to numpy array so that
    # the new matrix can be added to it
    if "confusion_matrix" in scores_buffer:
        scores_buffer["confusion_matrix"] = np.array(scores_buffer["confusion_matrix"])

    # Iterate over all metrics
    for metric in batch_scores.keys():
        # If metric isn't stored yet, add it
        if metric not in scores_buffer:
            scores_buffer[metric] = batch_scores[metric]

        else:
            # Add batch confusion matrix to the matrix based
            # on previous batches
            if metric == "confusion_matrix":
                scores_buffer[metric]+=batch_scores[metric]

            # For other different evaluation metrics
            # calculate the mean of previous results and
            # the batch results
            else:
                # If score is nan for the batch, continue
                if batch_scores[metric] == choices.SCORES_NAN_MARKER:
                    continue

                # If stored score for the metric is nan, change it to
                # current batch's score
                elif scores_buffer[metric] == choices.SCORES_NAN_MARKER:
                    scores_buffer[metric] = batch_scores[metric]

                # Otherwise, calculate average of the stored score and the batch score
                else:
                    scores_buffer[metric] = np.mean([scores_buffer[metric], batch_scores[metric]])

    # Convert confusion matric back to list so it can be dumped as json
    scores_buffer["confusion_matrix"] = scores_buffer["confusion_matrix"].astype("int").tolist()
    return scores_buffer


def scroll_and_score(generator: ElasticSearcher, evaluator_object: Evaluator, true_fact: str, pred_fact: str, true_fact_value: str = "", pred_fact_value: str = "", classes: List[Union[str, int]]=[], average: str = "macro", score_after_scroll: bool = True, n_batches: int = None, add_individual_results: bool = True) -> Tuple[dict, dict]:
    """ Scrolls over ES index and calculates scores."""

    true_labels = []
    pred_labels = []
    ks = 0

    # Store intermediate results
    scores = {}
    bin_scores = defaultdict(dict)

    for i, scroll_batch in enumerate(generator):

        # If scores are averaged after each scroll, clean label lists
        if score_after_scroll:
            true_labels = []
            pred_labels = []

        logging.getLogger(INFO_LOGGER).info(f"Scrolling through batch {i+1}/{n_batches}...")

        # Scroll over docs in the batch and retrieve true and predicted labels
        for raw_doc in scroll_batch:
            hit = raw_doc["_source"]
            facts = hit.get("texta_facts", [])

            # Collect lists of all fact_values in the document
            # corresponding to true and predicted facts
            true_fact_values = get_facts_by_name(facts, true_fact)
            pred_fact_values = get_facts_by_name(facts, pred_fact)

            # Binary evaluation
            if true_fact_value and pred_fact_value:
                true_label_i = 1 if true_fact_value in true_fact_values else 0
                pred_label_i = 1 if pred_fact_value in pred_fact_values else 0

                true_labels.append(true_label_i)
                pred_labels.append(pred_label_i)

            # Multilabel evaluation
            else:
                # If true fact value is not present, add an indicator for it
                if not true_fact_values and pred_fact_values:
                    true_fact_values = [choices.MISSING_TRUE_LABEL]

                # If pred fact value is not present, add an indicator for it
                elif not pred_fact_values and true_fact_values:
                    pred_fact_values = [choices.MISSING_PRED_LABEL]

                true_labels.append(true_fact_values)
                pred_labels.append(pred_fact_values)

        # If scores are averaged after each scroll, calculate scores
        # and store the averages
        if score_after_scroll:
            # Collect scores for the batch
            logging.getLogger(INFO_LOGGER).info(f"Evaluating batch {i+1}/{n_batches}...")
            batch_scores = get_scores(true_labels, pred_labels, classes, average, add_individual_results)
            bin_batch_scores = batch_scores.pop("bin_scores")

            scores = update_scores(scores, batch_scores)

            # For multiclass and multilabel classification, calculate individal scores per each label
            if add_individual_results and bin_batch_scores:

                # Iterate over all labels
                for label_class in bin_batch_scores:
                    bin_scores[label_class] = update_scores(bin_scores[label_class], bin_batch_scores[label_class])


            # Update model
            evaluator_object.precision = scores["precision"]
            evaluator_object.recall = scores["recall"]
            evaluator_object.f1_score = scores["f1_score"]
            evaluator_object.accuracy = scores["accuracy"]
            evaluator_object.confusion_matrix = json.dumps(scores["confusion_matrix"])
            evaluator_object.individual_results = json.dumps(bin_scores, ensure_ascii=False)
            evaluator_object.save()

    if not score_after_scroll:
        logging.getLogger(INFO_LOGGER).info(f"Start evaluation...")
        scores = get_scores(true_labels, pred_labels, classes, average, add_individual_results)
        # Convert confusion matrix to list so that in can be later be later dumpes as JSON
        scores["confusion_matrix"] = scores["confusion_matrix"].astype("int").tolist()
        bin_scores = scores.pop("bin_scores")

        # convert bin labels confusion matrix from numpy array to list
        for label in bin_scores:
            bin_scores[label]["confusion_matrix"] = bin_scores[label]["confusion_matrix"].astype("int").tolist()

    return (scores, bin_scores)
