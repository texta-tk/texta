import json

from django.core.exceptions import ValidationError
from texta_elastic.aggregator import ElasticAggregator


def validate_pos_label(data):
    """ For Tagger, TorchTagger and BertTagger.
    Checks if the inserted pos label is present in the fact values.
    """

    fact_name = data.get("fact_name")

    # If fact name is not selected, the value for pos label doesn't matter
    if not fact_name:
        return data

    indices = [index.get("name") for index in data.get("indices")]
    pos_label = data.get("pos_label")
    serializer_query = data.get("query")

    try:
        # If query is passed as a JSON string
        query = json.loads(serializer_query)
    except Exception as e:
        # if query is passed as a JSON dict
        query = serializer_query

    ag = ElasticAggregator(indices=indices, query=query)
    fact_values = ag.facts(size=10, filter_by_fact_name=fact_name, include_values=True)

    # If there exists exactly two possible values for the selected fact, check if pos label
    # is selected and if it is present in corresponding fact values.
    if len(fact_values) == 2:
        if not pos_label:
            raise ValidationError(f"The fact values corresponding to the selected query and fact '{fact_name}' are binary. You must specify param 'pos_label' for evaluation purposes. Allowed values for 'pos_label' are: {fact_values}")
        elif pos_label not in fact_values:
            raise ValidationError(f"The specified pos label '{pos_label}' is NOT one of the fact values for fact '{fact_name}'. Please select an existing fact value. Allowed fact values are: {fact_values}")
    return data
