import json
import logging

from rest_framework import serializers
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.project.models import Project
from toolkit.evaluator import choices
from toolkit.evaluator.models import Evaluator
from toolkit.evaluator.validators import (
    validate_average_function, validate_entity_facts, validate_evaluation_type,
    validate_fact_values_in_sync, validate_metric_restrictions, validate_fact, validate_fact_value,
)
from toolkit.serializer_constants import CommonModelSerializerMixin, IndicesSerializerMixin, ProjectResourceUrlSerializer, FavoriteModelSerializerMixin
from toolkit.settings import ERROR_LOGGER


class FilteredAverageSerializer(serializers.Serializer):
    min_count = serializers.IntegerField(
        default=choices.DEFAULT_MIN_COUNT,
        required=False,
        help_text=f"Required minimum number of tags present in the union set to include corresponding tag's scores to the average calculation.")
    max_count = serializers.IntegerField(
        default=choices.DEFAULT_MAX_COUNT,
        required=False,
        help_text=f"Required maximum number of tags present in the union set to include corresponding tag's scores to the average calculation."
    )
    metric_restrictions = serializers.JSONField(
        default={},
        validators=[validate_metric_restrictions],
        required=False,
        help_text=f"Score restrictions in format {{metric: {{'min_score: min_score, 'max_score': max_score}}, ...}}."
    )


class IndividualResultsSerializer(serializers.Serializer):
    min_count = serializers.IntegerField(
        default=choices.DEFAULT_MIN_COUNT,
        required=False,
        help_text=f"Required minimum number of tags present in the union set to include corresponding tag's scores to the output."
    )
    max_count = serializers.IntegerField(
        default=choices.DEFAULT_MAX_COUNT,
        required=False,
        help_text=f"Required maximum number of tags present in the union set to include corresponding tag's scores to the output."
    )
    metric_restrictions = serializers.JSONField(
        default={},
        validators=[validate_metric_restrictions],
        required=False,
        help_text=f"Score restrictions in format {{metric: {{'min_score: min_score, 'max_score': max_score}}, ...}}."
    )
    order_by = serializers.ChoiceField(
        default=choices.DEFAULT_ORDER_BY_FIELD,
        choices=choices.ORDERING_FIELDS_CHOICES,
        required=False,
        help_text=f"Field used for ordering the results."
    )
    order_desc = serializers.BooleanField(default=choices.DEFAULT_ORDER_DESC, required=False, help_text=f"Order results in descending order?")


class MisclassifiedExamplesSerializer(serializers.Serializer):
    min_count = serializers.IntegerField(default=choices.DEFAULT_MIN_MISCLASSIFIED_COUNT, required=False, help_text=f"Minimum frequency of the misclassified values to return.")
    max_count = serializers.IntegerField(default=choices.DEFAULT_MAX_MISCLASSIFIED_COUNT, required=False, help_text=f"Maximum frequency of the misclassified values to return.")
    top_n = serializers.IntegerField(default=choices.DEFAULT_N_MISCLASSIFIED_VALUES_TO_RETURN, required=False, help_text=f"Number of values to return per class.")


class EvaluatorSerializer(serializers.ModelSerializer, FavoriteModelSerializerMixin, CommonModelSerializerMixin, ProjectResourceUrlSerializer, IndicesSerializerMixin):
    query = serializers.JSONField(required=False, help_text="Query in JSON format", default=json.dumps(EMPTY_QUERY))

    true_fact = serializers.CharField(required=True, help_text=f"Fact name used as true label for mulilabel evaluation.")
    predicted_fact = serializers.CharField(required=True, help_text=f"Fact name used as predicted label for multilabel evaluation.")

    true_fact_value = serializers.CharField(required=False, default="", help_text=f"Fact value used as true label for binary evaluation.")
    predicted_fact_value = serializers.CharField(required=False, default="", help_text=f"Fact value used as predicted label for binary evaluation.")

    classes = serializers.SerializerMethodField(read_only=True)

    average_function = serializers.ChoiceField(
        choices=choices.AVG_CHOICES,
        default=choices.DEFAULT_AVG_FUNCTION,
        required=False,
        help_text=f"Sklearn average function. NB! Doesn't have any effect on entity evaluation."
    )

    es_timeout = serializers.IntegerField(default=choices.DEFAULT_ES_TIMEOUT, help_text=f"Elasticsearch scroll timeout in minutes.")
    scroll_size = serializers.IntegerField(
        min_value=1,
        max_value=10000,
        default=choices.DEFAULT_SCROLL_SIZE,
        help_text=f"How many documents should be returned by one Elasticsearch scroll."
    )

    add_individual_results = serializers.BooleanField(
        default=choices.DEFAULT_ADD_INDIVIDUAL_RESULTS,
        required=False,
        help_text=f"Only used for multilabel/multiclass evaluation. If enabled, individual label scores are calculated and stored as well."
    )

    add_misclassified_examples = serializers.BooleanField(
        default=choices.DEFAULT_ADD_MISCLASSIFIED_EXAMPLES,
        required=False,
        help_text=f"Only used for entity evaluation. If enabled, misclassified and partially overlapping values are stored and can be analyzed later."
    )

    evaluation_type = serializers.ChoiceField(
        choices=choices.EVALUATION_TYPE_CHOICES,
        default="multilabel",
        required=False,
        help_text=f"Specify the type of labelsets to evaluate."
    )
    token_based = serializers.BooleanField(
        default=choices.DEFAULT_TOKEN_BASED,
        required=False,
        help_text=f"If enabled, uses token-based entity evaluation, otherwise calculates the scores based on the spans of two value-sets."
    )

    field = serializers.CharField(
        default="",
        required=False,
        help_text=f"Field related to true and predicted facts. NB! This has effect only for evaluation_type='entity' and is only required if the selected facts have multiple different doc paths."
    )

    plot = serializers.SerializerMethodField()

    url = serializers.SerializerMethodField()


    def get_classes(self, item):
        try:
            return json.loads(item.classes)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(item)
            return []


    def validate_indices(self, value):
        """ Check if indices exist in the relevant project. """
        project_obj = Project.objects.get(id=self.context["view"].kwargs["project_pk"])
        for index in value:
            if index.get("name") not in project_obj.get_indices():
                raise serializers.ValidationError(f'Index "{index.get("name")}" is not contained in your project indices "{project_obj.get_indices()}"')
        return value


    def validate(self, data):
        """ Check if all inserted facts and fact values are present in the indices."""

        # For PATCH
        if len(data) == 1 and "description" in data:
            return data

        indices = [index.get("name") for index in data.get("indices")]
        query = data.get("query")
        if isinstance(query, str):
            query = json.loads(query)

        true_fact = data.get("true_fact")
        predicted_fact = data.get("predicted_fact")

        true_fact_value = data.get("true_fact_value")
        predicted_fact_value = data.get("predicted_fact_value")

        avg_function = data.get("average_function")
        evaluation_type = data.get("evaluation_type")

        doc_path = data.get("field")

        validate_fact(indices, query, true_fact)
        validate_fact(indices, query, predicted_fact)

        validate_fact_value(indices, query, true_fact, true_fact_value)
        validate_fact_value(indices, query, predicted_fact, predicted_fact_value)

        if evaluation_type == "entity":
            validate_entity_facts(indices, query, true_fact, predicted_fact, doc_path)

        validate_fact_values_in_sync(true_fact_value, predicted_fact_value)

        validate_average_function(avg_function, true_fact_value, predicted_fact_value)
        validate_evaluation_type(indices, query, evaluation_type, true_fact, predicted_fact, true_fact_value, predicted_fact_value, )

        return data


    class Meta:
        model = Evaluator
        fields = (
            "url", "author", "id", "description", "indices", "query", "true_fact", "predicted_fact", "true_fact_value", "predicted_fact_value",
            "average_function", "f1_score", "is_favorited", "classes", "precision", "recall", "accuracy", "confusion_matrix", "n_true_classes", "n_predicted_classes", "n_total_classes",
            "evaluation_type", "scroll_size", "es_timeout", "scores_imprecise", "score_after_scroll", "document_count", "add_individual_results", "plot", "tasks",
            "add_misclassified_examples", "evaluation_type", "token_based", "field"
        )

        read_only_fields = (
            "project", "f1_score", "is_favorited", "precision", "recall", "accuracy",
            "confusion_matrix", "n_true_classes", "n_predicted_classes", "n_total_classes",
            "evaluation_type", "document_count", "scores_imprecise", "score_after_scroll", "tasks"
        )
