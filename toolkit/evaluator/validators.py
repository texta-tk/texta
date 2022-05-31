import json

from typing import List
from copy import deepcopy
from django.core.exceptions import ValidationError

from texta_elastic.aggregator import ElasticAggregator
from toolkit.evaluator import choices


def validate_metric_restrictions(value: json):
    """ Check if metric restrictions JSON is in the correct format
        and contains correct keys and values.
    """
    # Allow empty value
    if not value:
        return {}
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValidationError(f"Incorrect input format: {type(value)}. Correct format is {type({})}.")
    for key, restrictions in list(value.items()):
        if not isinstance(restrictions, dict):
            raise ValidationError(f"Incorrect input format for dict value: {type(restrictions)}. Correct format is {type({})}.")
        if key not in choices.METRICS:
            raise ValidationError(f"Invalid key: {key}. Allowed metric keys are: {choices.METRICS}.")
        for restriction_key, restriction_value in list(restrictions.items()):
            if restriction_key not in choices.METRIC_RESTRICTION_FIELDS:
                raise ValidationError(f"Invalid restriction key: {restriction_key}. Allowed restriction keys are: {choices.METRIC_RESTRICTION_FIELDS}.")
            if not isinstance(restriction_value, float) and not isinstance(restriction_value, int):
                raise ValidationError(f"Invalid type for restriction '{key} - {restriction_key}': {type(restriction_value)}. Correct type is {type(1.0)}.")
            if not 0 <= restriction_value <= 1.0:
                raise ValidationError(f"Invalid value for restriction '{key} - {restriction_key}': {restriction_value}. The value should be in range [0.0, 1.0].")
    return value


def validate_fact(indices: List[str], query: dict, fact: str):
    """ Check if given fact exists in the selected indices. """
    ag = ElasticAggregator(indices=indices, query=deepcopy(query))
    fact_values = ag.get_fact_values_distribution(fact, fact_name_size=choices.DEFAULT_MAX_FACT_AGGREGATION_SIZE)
    if not fact_values:
        raise ValidationError(f"Fact '{fact}' not present in any of the selected indices ({indices}).")
    return True


def validate_entity_facts(indices: List[str], query: dict, true_fact: str, pred_fact: str, doc_path: str):
    """ Check if facts chosen for entity evaluation follow all the necessary requirements. """

    ag = ElasticAggregator(indices=indices, query=deepcopy(query))

    true_fact_doc_paths = ag.facts_abstract(key_field="fact", value_field="doc_path", filter_by_key=true_fact)
    pred_fact_doc_paths = ag.facts_abstract(key_field="fact", value_field="doc_path", filter_by_key=pred_fact)

    if doc_path:
        if doc_path not in true_fact_doc_paths:
            raise ValidationError(f"The selected true_fact ('{true_fact}') doesn't contain any instances corresponding to the selected field('{doc_path}').")

        if doc_path not in pred_fact_doc_paths:
            raise ValidationError(f"The selected predicted_fact ('{pred_fact}') doesn't contain any instances corresponding to the selected field('{doc_path}').")

    if not doc_path:
        if set(true_fact_doc_paths) != set(pred_fact_doc_paths):
            raise ValidationError(f"The doc paths for true and predicted facts are different (true = {true_fact_doc_paths}; predicted = {pred_fact_doc_paths}). Please make sure you are evaluating facts based on the same fields.")

        if len(true_fact_doc_paths) > 1:
            raise ValidationError(f"Selected true fact ({true_fact}) is related to two or more fields {true_fact_doc_paths}, but the value for parameter 'field' isn't defined. Please define parameter 'field'.")

        if len(pred_fact_doc_paths) > 1:
            raise ValidationError(f"Selected predicted fact ({pred_fact}) is related to two or more fields {pred_fact_doc_paths}, but the value for parameter 'field' isn't defined. Please define parameter 'field'.")

    return True


def validate_evaluation_type(indices: List[str], query: dict, evaluation_type: str, true_fact: str, pred_fact: str, true_value: str, pred_value: str):
    """ Checks if the chosen facts (and values) are applicable for the chosen evaluation type.
    """

    if evaluation_type == "binary":
        if not true_value or not pred_value:
            raise ValidationError(f"Please specify true and predicted values for evaluation type 'binary'.")
    #elif evaluation_type == "multilabel":
    #    if true_value or pred_value:
    #        raise ValidationError(f"Please leave true and predicted values unspeficied for evaluation type 'multilabel'.")
    elif evaluation_type == "entity":
        if true_value or pred_value:
            raise ValidationError(f"Please leave true and predicted values unspeficied for evaluation type 'entity'.")

        ag = ElasticAggregator(indices=indices, query=deepcopy(query))

        true_fact_results = ag.facts_abstract(key_field="fact", value_field="spans", filter_by_key=true_fact, size=5)
        pred_fact_results = ag.facts_abstract(key_field="fact", value_field="spans", filter_by_key=pred_fact, size=5)

        if len(true_fact_results) == 1:
            spans = json.loads(true_fact_results[0])
            if not spans[0] or (spans[0][0] == 0 and spans[0][1] == 0):
                raise ValidationError(f"Did not find non-zero spans for selected true fact '{true_fact}'. Please make sure to use facts with existing spans for evaluation_type 'entity'.")

        if len(pred_fact_results) == 1:
            spans = json.loads(pred_fact_results[0])
            if not spans[0] or (spans[0][0] == 0 and spans[0][1] == 0):
                raise ValidationError(f"Did not find non-zero spans for selected predicted fact '{pred_fact}'. Please make sure to use facts with existing spans for evaluation_type 'entity'.")

    return True


def validate_fact_value(indices: List[str], query: dict, fact: str, fact_value: str):
    """ Check if given fact value exists under given fact. """
    # Fact value is allowed to be empty
    if not fact_value:
        return True

    ag = ElasticAggregator(indices=indices, query=deepcopy(query))

    fact_values = ag.facts(size=choices.DEFAULT_MAX_AGGREGATION_SIZE, filter_by_fact_name=fact, include_values=True)
    if fact_value not in fact_values:
        raise ValidationError(f"Fact value '{fact_value}' not in the list of fact values for fact '{fact}'.")
    return True


def validate_average_function(average_function: str, true_fact_value: str, pred_fact_value: str):
    """ Check if selected average function is suitable for the evaluation type. """

    if not true_fact_value and not pred_fact_value and average_function == "binary":
        raise ValidationError(f"Average function '{average_function}' can only be used for binary evaluation. Available average functions for non-binary evaluation are: {choices.MULTILABEL_AVG_FUNCTIONS}.")

    if true_fact_value and pred_fact_value and average_function == "samples":
        raise ValidationError(f"Average function '{average_function}' can only be used for multilabel evaluation. Available average functions for binary evaluation are: {choices.BINARY_AVG_FUNCTIONS}.")

    return True


def validate_fact_values_in_sync(true_fact_value: str, pred_fact_value: str):
    """ Check of both fact values are either specified or not specified.
    """
    if (true_fact_value and not pred_fact_value) or (pred_fact_value and not true_fact_value):
        raise ValidationError(f"If one of the fact values is specified, the other one should be too. Current fact values: true_fact_value: '{true_fact_value}', pred_fact_value: '{pred_fact_value}'.")
    return True
