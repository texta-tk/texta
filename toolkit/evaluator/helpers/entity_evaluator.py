import os
import json
import logging

from collections import defaultdict
from typing import List, Union, Tuple, Dict
from texta_elastic.searcher import ElasticSearcher

from toolkit.evaluator.models import Evaluator
from toolkit.evaluator import choices

from toolkit.settings import INFO_LOGGER, ERROR_LOGGER


def separate_facts_with_multispans(texta_facts: List[dict]) -> List[dict]:
    """ Separates facts with multiple spans. E.g:
    [{"fact": "PER", "str_val": "Joe", "spans": "[[3,6], [17,20], [35,38]]"}] ->
    [
        {"fact": "PER", "str_val": "Joe", "spans": "[[3,6]]"},
        {"fact": "PER", "str_val": "Joe", "spans": "[[17,20]]"},
        {"fact": "PER", "str_val": "Joe", "spans": "[[35,38]]"}
    ]
    """
    new_facts = []

    for fact in texta_facts:
        spans = json.loads(fact["spans"])
        for span in spans:
            new_fact = {}
            for key, val in list(fact.items()):
                if key != "spans":
                    new_fact[key] = val
            new_fact["spans"] = json.dumps([span])
            new_facts.append(new_fact)

    return new_facts


def filter_facts_by_name_and_path(texta_facts: List[dict], name: str, doc_path: str = "") -> List[dict]:
    """ Filters facts based on fact name.
    """
    if not doc_path:
        filtered_facts = [fact for fact in texta_facts if fact["fact"] == name]
    else:
        filtered_facts = [fact for fact in texta_facts if fact["fact"] == name and fact["doc_path"] == doc_path]
    return filtered_facts


def facts_to_span_labels(texta_facts: List[dict], as_str: bool = True) -> Union[List[str], List[Tuple[int, str]]]:
    """ Converts texta_facts into span-based labels. Depending on the value of param `as_str`,
    the function returns either a list of string s(e.g. ['0_[[123,134]]', '3_[[12,34]]']) or
    a list of tuples (e.g. [(0, [[123,134]]), (3, [[12,34]])]).
    """
    labels = []

    for fact in texta_facts:
        if json.loads(fact["spans"])[0]:
            if "sent_index" in fact:
                if as_str:
                    label = f"{fact['sent_index']}_{fact['spans']}"
                else:
                    label = (fact["sent_index"], json.loads(fact["spans"]))
            else:
                if as_str:
                    label = f"0_{fact['spans']}"
                else:
                    label = (0, json.loads(fact["spans"]))
            labels.append(label)
    out = sorted(list(set(labels))) if as_str else labels
    return out


def span_labels_to_dict(span_labels: List[Tuple[int, str]]) -> Dict[int, List[List[int]]]:
    """ Converts span labels into a dict with sent indices as keys and spans as values.
    E.g: [(0, [[2,13]]), (0, [[45,56]]), (3, [[17,26]])] -> {0: [[2,13], [45,56]], 3: [[17, 26]]}
    """
    facts_dict = defaultdict(list)
    for sent_index, spans in span_labels:
        for span in spans:
            facts_dict[sent_index].append(span)
    return facts_dict


def get_classes(true_labels: List[str], pred_labels: List[str]) -> List[str]:
    """ Returns the union set of true and pred labels.
    """
    classes = true_labels + pred_labels
    return list(set(classes))


def value_spans_to_token_spans(span: List[int], text: str) -> List[str]:
    """ Converts value-based spans into token-based spans. E.g:
    span = [0, 10], text = 'John Smith goes to Washington.' -> ['[[0, 4]]', '[[5,10]]']
    (tokens 'John' and 'Smith' are assigned separate spans).
    """
    entity = text[span[0]: span[1]]
    tokens = entity.split()
    new_spans = []
    start_span = span[0]
    for i, token in enumerate(tokens):
        end_span = start_span + len(token)
        spans = [start_span, end_span]
        new_spans.append(json.dumps(spans))
        start_span = end_span
        start_span+=1
    return new_spans


def get_text(doc: dict, doc_path: str) -> str:
    """ Retrieve text from a given (potentially nested) field.
    """
    doc_path_tokens = doc_path.split(".")
    if doc_path_tokens[0] not in doc:
        raise Exception(f"Couldn't detect field '{doc_path}' from the given document.")

    text = doc[doc_path_tokens[0]]
    pointer = 1

    while isinstance(text, dict) or pointer < len(doc_path_tokens):
        if doc_path_tokens[pointer] not in text:
            raise Exception(f"Couldn't detect field '{doc_path}' from the given document.")
        text = text[doc_path_tokens[pointer]]
        pointer+=1

    if not isinstance(text, str):
        raise Exception(f"Did not find string content corresponding to field '{doc_path}'.")
    return text


def get_token_spans(sent_index: int, label_dict: Dict[int, list], text: str):
    """ Recalculate spans (value spans -> token spans).
    """
    token_spans = []
    if sent_index in label_dict:
        for span in label_dict[sent_index]:
            token_spans_i = value_spans_to_token_spans(span, text)
            token_spans.extend(token_spans_i)
    return token_spans


def calculate_prediction_scores(tps: int, tns: int, fps: int, fns: int, zero_denominator_value: int = -1) -> Dict[str, float]:
    """ Calculates precision, recall, recall, accuracy and f1-score based on given
    true positives, true negatives, false positives and false negatives.
    """
    precision  = tps/(tps+fps) if tps+fps != 0 else zero_denominator_value
    recall = tps/(tps+fns) if tps+fns != 0 else zero_denominator_value
    accuracy = (tps + tns)/(tps+tns+fps+fns) if tps+tns+fps+fns != 0 else zero_denominator_value
    f1 = 2*(precision*recall)/(precision+recall) if precision + recall != 0 else zero_denominator_value
    return {"precision": precision, "recall": recall, "accuracy": accuracy, "f1_score": f1}



def get_tps_fps_tns_fns(text: str, true_spans: List[str], pred_spans: List[str]) -> Tuple[int, int, int, int]:
    """ Count token-based true positives, false positives, true negatives, false negatives in a document.
    """

    tps = 0
    fps = 0
    tns = 0
    fns = 0

    focus_label = "ENT"
    out_label = "O"

    tokens = text.split()

    start_span = 0

    for j, token in enumerate(tokens):
        end_span = start_span + len(token)
        spans = [start_span, end_span]

        # Assign either OUT_LABEL or FOCUS_LABEL to the current true token
        if json.dumps(spans) in true_spans:
            true_label_j = focus_label
        else:
            true_label_j = out_label

        # Assign either OUT_LABEL or FOCUS_LABEL to the current pred token
        if json.dumps(spans) in pred_spans:
            pred_label_j = focus_label
        else:
            pred_label_j = out_label

        # Increase the count of true positives, if necessary
        if (true_label_j == focus_label) and (pred_label_j == focus_label):
            tps+=1

        # Increase the count of true negatives, if necessary
        elif (true_label_j != focus_label) and (pred_label_j != focus_label):
            tns+=1

        # Increase the count of false negatives, if necessary
        elif (true_label_j == focus_label) and (pred_label_j != focus_label):
            fns+=1

        # Increase the count of false positives, if necessary
        elif (true_label_j != focus_label) and (pred_label_j == focus_label):
            fps+=1

        start_span = end_span
        start_span+=1

    return (tps, fps, tns, fns)


def get_labels(sent_index: int, label_dict: Dict[int, list], as_str: bool = False) -> Union[List[str], List[list]]:
    """ Get labels corresponding to the given sent index.
    """
    labels = []
    if sent_index in label_dict:
        if as_str:
            labels = [json.dumps(l, ensure_ascii=False) for l in label_dict[sent_index]]
        else:
            labels = label_dict[sent_index]
    return labels


def get_value_based_tps(sent_index: int, true_dict: Dict[int, list], pred_dict: Dict[int, list]) -> int:
    """ Calculate the number of true positives for value based evaluation.
    """
    true_labels = get_labels(sent_index, true_dict, as_str = True)
    pred_labels = get_labels(sent_index, pred_dict, as_str = True)

    tps = len(list(set(true_labels).intersection(set(pred_labels))))
    return tps


def get_unique_span_labels(sent_index: int, true_dict: Dict[int, list], pred_dict: Dict[int, list]) -> Tuple[List[list], List[list]]:
    """ Get false positives and false negatives.
    """
    true_labels = get_labels(sent_index, true_dict, as_str = True)
    pred_labels = get_labels(sent_index, pred_dict, as_str = True)

    # Get unique true and pred span labels
    # NB! Unique pred labels correspond to false positives and unique true labels correspond to false negatives
    true_unique = [json.loads(l) for l in list(set(true_labels).difference(set(pred_labels)))]
    pred_unique = [json.loads(l) for l in list(set(pred_labels).difference(set(true_labels)))]

    true_unique.sort(key = lambda x: x[0])
    pred_unique.sort(key = lambda x: x[0])

    return  (true_unique, pred_unique)


def process_batch(doc_batch: List[dict], doc_path: str, pred_fact_name: str, true_fact_name: str, token_based: bool = True, add_misclassified_examples: bool = True) -> Dict[str, int]:
    """ Process a batch of documents.
    """

    tps = 0
    fps = 0
    fns = 0
    tns = 0

    subset_vals = []
    superset_vals = []
    partial_vals = []
    fp_vals = []
    fn_vals = []

    for i, raw_doc in enumerate(doc_batch):

        doc = raw_doc["_source"]

        text = get_text(doc, doc_path)
        texta_facts = doc.get("texta_facts", [])

        # Filter out relevant facts
        true_facts = filter_facts_by_name_and_path(texta_facts, true_fact_name, doc_path)
        pred_facts = filter_facts_by_name_and_path(texta_facts, pred_fact_name, doc_path)

        # Convert facts to labels in suitable format
        true_labels = facts_to_span_labels(true_facts, as_str = False)
        pred_labels = facts_to_span_labels(pred_facts, as_str = False)

        # Convert retrieved span labels into dicts based on sent indices
        true_dict = span_labels_to_dict(true_labels)
        pred_dict = span_labels_to_dict(pred_labels)

        # Check if nonzero keys exists. If they do, we know that we are dealing
        # with sentence-level spans
        nonzero_true_keys = [key for key in true_dict.keys() if key != 0]
        nonzero_pred_keys = [key for key in pred_dict.keys() if key != 0]
        nonzero_keys = set(nonzero_true_keys + nonzero_pred_keys)

        if nonzero_keys:
            texts = [t.strip() for t in text.split("\n")]
        else:
            texts = [text]

        for j, text in enumerate(texts):

            # If calculate scores based on tokens
            if token_based:
                # NB! Doesn't differentiate B-entities and I-entities!
                true_spans = get_token_spans(j, true_dict, text)
                pred_spans = get_token_spans(j, pred_dict, text)
                tps_j, fps_j, tns_j, fns_j = get_tps_fps_tns_fns(text, true_spans, pred_spans)

                # Add document based true positives, false positives, true negatives and false true_negatives
                # to the global values.
                tps+=tps_j
                fps+=fps_j
                tns+=tns_j
                fns+=fns_j

            true_unique, pred_unique = get_unique_span_labels(j, true_dict, pred_dict)


            used_true_spans = []
            used_pred_spans = []

            # Retrieve values of partial overlaps
            for start_p, end_p in pred_unique:
                for start_t, end_t in true_unique:

                    # If the predicted value is a substring of the true value, e.g. "EDGAR" vs. "EDGAR Sa"
                    if start_p >= start_t and end_p <= end_t:
                        subset_val = json.dumps({"true": text[start_t: end_t], "pred": text[start_p: end_p]}, ensure_ascii=False)
                        subset_vals.append(subset_val)
                        used_pred_spans.append(json.dumps([start_p, end_p], ensure_ascii=False))
                        used_true_spans.append(json.dumps([start_t, end_t], ensure_ascii=False))

                    # If the predicted value has a parital overlap with the true value, e.g. "Anton HANSEN" vs. "HANSEN Tammsaare"
                    elif (start_p < start_t and end_p > start_t and end_p < end_t) or (start_p > start_t and start_p <= end_t and end_p > end_t):
                        partial_val = json.dumps({"true": text[start_t: end_t], "pred": text[start_p: end_p]}, ensure_ascii=False)
                        partial_vals.append(partial_val)
                        used_pred_spans.append(json.dumps([start_p, end_p], ensure_ascii=False))
                        used_true_spans.append(json.dumps([start_t, end_t], ensure_ascii=False))

                    # If the predicted value is a superstring of the true value, e.g. "EDGAR SAVISAAR" vs. "SAVISAAR"
                    elif (start_p < start_t and end_p > end_t):
                        superset_val = json.dumps({"true": text[start_t: end_t], "pred": text[start_p: end_p]}, ensure_ascii=False)
                        superset_vals.append(superset_val)
                        used_pred_spans.append(json.dumps([start_p, end_p], ensure_ascii=False))
                        used_true_spans.append(json.dumps([start_t, end_t], ensure_ascii=False))

            true_i_keep_str = [json.dumps(l, ensure_ascii=False) for l in true_unique]
            pred_i_keep_str = [json.dumps(l, ensure_ascii=False) for l in pred_unique]
            fn_spans = [json.loads(l) for l in list(set(true_i_keep_str).difference(set(used_true_spans)))]
            fp_spans = [json.loads(l) for l in list(set(pred_i_keep_str).difference(set(used_pred_spans)))]

            fn_vals_i = [text[s0: s1] for s0, s1 in fn_spans]
            fp_vals_i = [text[s0: s1] for s0, s1 in fp_spans]
            fn_vals.extend(fn_vals_i)
            fp_vals.extend(fp_vals_i)

            if not token_based:
                if not true_unique and not pred_unique:
                    # Not sure how to score true negatives
                    tns+= 1
                tps+= get_value_based_tps(j, true_dict, pred_dict)
                fps+= len(fp_spans)
                fns+= len(fn_spans)

    counts = {"tps": tps, "tns": tns, "fns": fns, "fps": fps}
    values = {"substrings": subset_vals, "superstrings": superset_vals, "partial": partial_vals, "false_negatives": fn_vals, "false_positives": fp_vals}
    return {"counts": counts, "values": values}



def scroll_and_score_entity(generator: ElasticSearcher, evaluator_object: Evaluator, true_fact: str, pred_fact: str, doc_path: str, token_based: bool, n_batches: int = None, add_misclassified_examples: bool = True) -> Tuple[dict, dict]:
    """ Scrolls over ES index and calculates scores."""

    total_counts = {
        "tps": 0,
        "tns": 0,
        "fns": 0,
        "fps": 0
    }
    misclassified = {
        "substrings": defaultdict(int),
        "superstrings": defaultdict(int),
        "partial": defaultdict(int),
        "false_negatives": defaultdict(int),
        "false_positives": defaultdict(int)
    }

    for i, scroll_batch in enumerate(generator):

        logging.getLogger(INFO_LOGGER).info(f"Scrolling through batch {i+1}/{n_batches}...")

        batch_results = process_batch(scroll_batch, doc_path=doc_path, pred_fact_name=pred_fact, true_fact_name=true_fact, token_based=token_based, add_misclassified_examples=add_misclassified_examples)

        batch_counts = batch_results["counts"]
        batch_values = batch_results["values"]

        for key, count in list(batch_counts.items()):
            total_counts[key]+=count

        for key, values in list(batch_values.items()):
            for value in values:
                misclassified[key][value]+=1

    tps=total_counts["tps"]
    tns=total_counts["tns"]
    fps=total_counts["fps"]
    fns=total_counts["fns"]

    scores = calculate_prediction_scores(tps=tps, tns=tns, fps=fps, fns=fns, zero_denominator_value=-1)


    confusion_matrix = [[tns, fps], [fns, tps]]
    scores["confusion_matrix"] = confusion_matrix

    # Update model
    evaluator_object.precision = scores["precision"]
    evaluator_object.recall = scores["recall"]
    evaluator_object.f1_score = scores["f1_score"]
    evaluator_object.accuracy = scores["accuracy"]
    evaluator_object.confusion_matrix = json.dumps(confusion_matrix)

    evaluator_object.n_true_classes = tps + fns
    evaluator_object.n_predicted_classes = tps + fps
    evaluator_object.n_total_classes = tps + fns + fps # tns aren't included!

    misclassified_new = {}

    if add_misclassified_examples:
        for key, value_dict in list(misclassified.items()):
            value_dict = dict(value_dict)
            value_list = sorted(list(value_dict.items()), key=lambda x: x[1], reverse=True)
            if key not in ["false_negatives", "false_positives"]:
                value_list = [{"value": json.loads(s), "count": c} for s, c in value_list]
            else:
                value_list = [{"value": s, "count": c} for s, c in value_list]
            misclassified_new[key] = value_list[:choices.MAX_MISCLASSIFIED_VALUES_STORED]

        evaluator_object.misclassified_examples = json.dumps(misclassified_new, ensure_ascii=False)
    evaluator_object.save()

    return (scores, misclassified_new)
