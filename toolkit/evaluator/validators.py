import json

from typing import List

from django.core.exceptions import ValidationError

from toolkit.elastic.tools.aggregator import ElasticAggregator
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


def validate_fact(indices: List[str], fact: str):
    """ Check if given fact exists in the selected indices. """
    ag = ElasticAggregator(indices=indices)
    fact_values = ag.get_fact_values_distribution(fact)
    if not fact_values:
        raise ValidationError(f"Fact '{fact}' not present in any of the selected indices ({indices}).")
    return True


def validate_fact_value(indices: List[str], fact: str, fact_value: str):
    """ Check if given fact value exists under given fact. """
    # Fact value is allowed to be empty
    if not fact_value:
        return True

    ag = ElasticAggregator(indices=indices)

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
