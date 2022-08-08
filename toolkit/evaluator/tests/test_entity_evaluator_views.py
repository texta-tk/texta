import json
import pathlib
from io import BytesIO
from time import sleep

import numpy as np
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.query import Query

from toolkit.core.task.models import Task
from toolkit.evaluator import choices
from toolkit.evaluator.models import Evaluator as EvaluatorObject
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import (TEST_INDEX_ENTITY_EVALUATOR, TEST_KEEP_PLOT_FILES, TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import (
    create_test_user,
    print_output,
    project_creation,
    remove_file
)


@override_settings(CELERY_ALWAYS_EAGER=True)
class EntityEvaluatorObjectViewTests(APITransactionTestCase):
    def setUp(self):
        # Owner of the project
        self.test_index = reindex_test_dataset(from_index=TEST_INDEX_ENTITY_EVALUATOR)
        self.user = create_test_user("EvaluatorOwner", "my@email.com", "pw")
        self.project = project_creation("EvaluatorTestProject", self.test_index, self.user)
        self.project.users.add(self.user)
        self.url = f"{TEST_VERSION_PREFIX}/projects/{self.project.id}/evaluators/"
        self.project_url = f"{TEST_VERSION_PREFIX}/projects/{self.project.id}"

        self.true_fact_name = "PER"
        self.pred_fact_name = "PER_CRF_30"

        self.true_fact_name_sent_index = "PER_SENT"
        self.pred_fact_name_sent_index = "PER_CRF_31_SENT"

        self.fact_name_no_spans = "PER_FN_REGEX_NO_SPANS"

        self.fact_name_different_doc_paths = "PER_DOUBLE"

        self.core_variables_url = f"{TEST_VERSION_PREFIX}/core_variables/5/"

        # TODO! Construct a test query
        self.fact_names_to_filter = [self.true_fact_name, self.pred_fact_name]
        self.test_query = Query()
        self.test_query.add_facts_filter(self.fact_names_to_filter, [], operator="must")
        self.test_query = self.test_query.__dict__()

        self.client.login(username="EvaluatorOwner", password="pw")

        self.token_based_evaluator_id = None
        self.value_based_evaluator_id = None
        self.token_based_sent_index_evaluator_id = None
        self.value_based_sent_index_evaluator_id = None


    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index=self.test_index, ignore=[400, 404])


    def test(self):

        self.run_test_invalid_fact_name()
        self.run_test_invalid_fact_without_spans()
        self.run_test_invalid_doc_path()
        self.run_test_invalid_facts_have_different_doc_paths()
        self.run_test_invalid_fact_has_multiple_paths_field_name_unspecified()
        self.run_test_entity_evaluation_token_based()
        self.run_test_entity_evaluation_token_based_sent_index()
        self.run_test_entity_evaluation_value_based()
        self.run_test_entity_evaluation_value_based_sent_index()
        self.run_test_individual_results_view_entity(self.token_based_evaluator_id)
        self.run_test_filtered_average_view_entity(self.token_based_evaluator_id)
        self.run_test_misclassified_examples_get(self.token_based_evaluator_id)
        self.run_test_misclassified_examples_get(self.value_based_evaluator_id)
        self.run_test_misclassified_examples_get(self.token_based_sent_index_evaluator_id)
        self.run_test_misclassified_examples_get(self.value_based_sent_index_evaluator_id)
        self.run_test_misclassified_examples_post(self.token_based_evaluator_id)
        self.run_test_misclassified_examples_post(self.value_based_evaluator_id)
        self.run_test_misclassified_examples_post(self.token_based_sent_index_evaluator_id)
        self.run_test_misclassified_examples_post(self.value_based_sent_index_evaluator_id)
        self.run_test_entity_evaluation_with_query()
        self.run_export_import(self.token_based_evaluator_id)
        self.run_reevaluate(self.token_based_evaluator_id)
        self.run_delete(self.token_based_evaluator_id)
        self.run_patch(self.value_based_evaluator_id)


    def add_cleanup_files(self, evaluator_id: int):
        try:
            evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        except:
            pass
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, evaluator_object.plot.path)


    def run_test_invalid_fact_name(self):
        """
        Check if evaluator endpoint throws an error if one of the
        selected fact names is not present in the selected indices.
        """
        invalid_payloads = [
            {
                "true_fact": self.true_fact_name,
                "predicted_fact": "INVALID_FACT_NAME"
            },
            {
                "true_fact": "INVALID_FACT_NAME",
                "predicted_fact": self.pred_fact_name
            }
        ]
        main_payload = {
            "description": "Test invalid fact name",
            "indices": [{"name": self.test_index}],
            "evaluation_type": "entity"
        }
        for invalid_payload in invalid_payloads:
            payload = {**main_payload, **invalid_payload}
            response = self.client.post(self.url, payload, format="json")
            print_output("entity_evaluator:run_test_invalid_fact_name:response.data", response.data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_test_invalid_fact_without_spans(self):
        """
        Check if evaluator endpoint throws an error if one of the
        selected fact names has only zero-valued spans.
        """
        invalid_payloads = [
            {
                "true_fact": self.true_fact_name,
                "predicted_fact": self.fact_name_no_spans
            },
            {
                "true_fact": self.fact_name_no_spans,
                "predicted_fact": self.pred_fact_name
            }
        ]
        main_payload = {
            "description": "Test invalid fact without spans",
            "indices": [{"name": self.test_index}],
            "evaluation_type": "entity"
        }
        for invalid_payload in invalid_payloads:
            payload = {**main_payload, **invalid_payload}
            response = self.client.post(self.url, payload, format="json")
            print_output("entity_evaluator:run_test_invalid_fact_without_spans:response.data", response.data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_test_invalid_doc_path(self):
        """
        Check if evaluator endpoint throws an error if the
        selected doc_path is invalid.
        """
        invalid_payloads = [
            {
                "true_fact": self.true_fact_name,
                "predicted_fact": self.pred_fact_name
            }
        ]
        main_payload = {
            "description": "Test invalid doc_path (field)",
            "indices": [{"name": self.test_index}],
            "evaluation_type": "entity",
            "field": "brr"
        }
        for invalid_payload in invalid_payloads:
            payload = {**main_payload, **invalid_payload}
            response = self.client.post(self.url, payload, format="json")
            print_output("entity_evaluator:run_test_invalid_doc_path:response.data", response.data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_test_invalid_facts_have_different_doc_paths(self):
        """
        Check if evaluator endpoint throws an error if the
        selected facts have different doc paths.
        """
        invalid_payloads = [
            {
                "true_fact": self.true_fact_name,
                "predicted_fact": self.pred_fact_name_sent_index
            },
            {
                "true_fact": self.true_fact_name_sent_index,
                "predicted_fact": self.pred_fact_name
            }
        ]
        main_payload = {
            "description": "Test invalid: facts have different doc paths (fields)",
            "indices": [{"name": self.test_index}],
            "evaluation_type": "entity"
        }
        for invalid_payload in invalid_payloads:
            payload = {**main_payload, **invalid_payload}
            response = self.client.post(self.url, payload, format="json")
            print_output("entity_evaluator:run_test_invalid_facts_have_different_doc_paths:response.data", response.data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_test_invalid_fact_has_multiple_paths_field_name_unspecified(self):
        """
        Check if evaluator endpoint throws an error if one of the
        selected fact names is related to more than one doc path,
        but the user hasn't specified the field.
        """
        invalid_payloads = [
            {
                "true_fact": self.true_fact_name,
                "predicted_fact": self.fact_name_different_doc_paths
            },
            {
                "true_fact": self.fact_name_different_doc_paths,
                "predicted_fact": self.pred_fact_name
            }
        ]
        main_payload = {
            "description": "Test invalid fact without spans",
            "indices": [{"name": self.test_index}],
            "evaluation_type": "entity"
        }
        for invalid_payload in invalid_payloads:
            payload = {**main_payload, **invalid_payload}
            response = self.client.post(self.url, payload, format="json")
            print_output("entity_evaluator:run_test_invalid_fact_has_multiple_paths_field_name_unspecified:response.data", response.data)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_test_individual_results_view_entity(self, evaluator_id: int):
        """ Test individual_results endpoint for entity evaluators."""

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        evaluation_type = evaluator_object.evaluation_type

        url = f"{self.url}{evaluator_id}/individual_results/"

        default_payload = {}

        response = self.client.post(url, default_payload, format="json")
        print_output(f"entity_evaluator:run_test_individual_results_view_binary:{evaluation_type}:default_payload:response.data:", response.data)

        # The usage of the endpoint is not available for binary evaluators
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        self.add_cleanup_files(evaluator_id)


    def run_test_filtered_average_view_entity(self, evaluator_id: int):
        """ Test filtered_average endpoint for binary evaluators. """

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        evaluation_type = evaluator_object.evaluation_type

        url = f"{self.url}{evaluator_id}/filtered_average/"

        default_payload = {}

        response = self.client.post(url, default_payload, format="json")
        print_output(f"entity_evaluator:run_test_filtered_average_view_entity:{evaluation_type}:default_payload:response.data:", response.data)

        # The usage of the endpoint is not available for binary evaluators
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        self.add_cleanup_files(evaluator_id)


    def run_test_entity_evaluation_token_based(self):
        """ Test token-based entity evaluation. """

        payload = {
            "description": "Test token-based entity evaluation",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name,
            "predicted_fact": self.pred_fact_name,
            "scroll_size": 50,
            "add_misclassified_examples": True,
            "token_based": True,
            "evaluation_type": "entity"

        }

        expected_scores = {
            "accuracy": 0.99,
            "precision": 0.84,
            "recall": 0.85,
            "f1_score": 0.84
        }

        response = self.client.post(self.url, payload, format="json")
        print_output(f"entity_evaluator:run_test_entity_evaluation_token_based:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        evaluator_id = response.data["id"]
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        task_object = evaluator_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output(f"entity_evaluator:run_test_entity_evaluation_token_based: waiting for evaluation task to finish, current status:", task_object.status)
            sleep(1)

        evaluator_json = evaluator_object.to_json()
        evaluator_json.pop("misclassified_examples")

        print_output(f"entity_evaluator:run_test_entity_evaluation_token_based:evaluator_object.json:", evaluator_json)

        for metric in choices.METRICS:
            self.assertEqual(round(evaluator_json[metric], 2), expected_scores[metric])

        self.assertEqual(evaluator_object.n_total_classes, 877)
        self.assertEqual(evaluator_object.n_true_classes, 757)
        self.assertEqual(evaluator_object.n_predicted_classes, 760)

        cm = np.array(json.loads(evaluator_object.confusion_matrix))
        cm_size = np.shape(cm)

        self.assertEqual(2, cm_size[0])
        self.assertEqual(2, cm_size[1])

        self.assertEqual(evaluator_object.document_count, 100)
        self.assertEqual(evaluator_object.add_individual_results, False)
        self.assertEqual(evaluator_object.scores_imprecise, False)
        self.assertEqual(evaluator_object.token_based, True)
        self.assertEqual(evaluator_object.evaluation_type, "entity")

        self.token_based_evaluator_id = evaluator_id

        self.add_cleanup_files(evaluator_id)


    def run_test_entity_evaluation_token_based_sent_index(self):
        """ Test token-based entity evaluation with sentence-level spans. """

        payload = {
            "description": "Test token-based entity evaluation with sentence-level spans",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name_sent_index,
            "predicted_fact": self.pred_fact_name_sent_index,
            "scroll_size": 50,
            "add_misclassified_examples": True,
            "token_based": True,
            "evaluation_type": "entity"

        }

        expected_scores = {
            "accuracy": 1.0,
            "precision": 0.93,
            "recall": 0.90,
            "f1_score": 0.92
        }

        response = self.client.post(self.url, payload, format="json")
        print_output(f"entity_evaluator:run_test_entity_evaluation_token_based:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        evaluator_id = response.data["id"]
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        task_object = evaluator_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output(f"entity_evaluator:run_test_entity_evaluation_token_based_sent_index: waiting for evaluation task to finish, current status:", task_object.status)
            sleep(1)

        evaluator_json = evaluator_object.to_json()
        evaluator_json.pop("misclassified_examples")

        print_output(f"entity_evaluator:run_test_entity_evaluation_token_based_sent_index:evaluator_object.json:", evaluator_json)

        for metric in choices.METRICS:
            self.assertEqual(round(evaluator_json[metric], 2), expected_scores[metric])

        self.assertEqual(evaluator_object.n_total_classes, 802)
        self.assertEqual(evaluator_object.n_true_classes, 754)
        self.assertEqual(evaluator_object.n_predicted_classes, 726)

        cm = np.array(json.loads(evaluator_object.confusion_matrix))
        cm_size = np.shape(cm)

        self.assertEqual(2, cm_size[0])
        self.assertEqual(2, cm_size[1])

        self.assertEqual(evaluator_object.document_count, 100)
        self.assertEqual(evaluator_object.add_individual_results, False)
        self.assertEqual(evaluator_object.scores_imprecise, False)
        self.assertEqual(evaluator_object.token_based, True)
        self.assertEqual(evaluator_object.evaluation_type, "entity")

        self.token_based_sent_index_evaluator_id = evaluator_id

        self.add_cleanup_files(evaluator_id)


    def run_test_entity_evaluation_value_based(self):
        """ Test value-based entity evaluation. """

        payload = {
            "description": "Test value-based entity evaluation",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name,
            "predicted_fact": self.pred_fact_name,
            "scroll_size": 50,
            "add_misclassified_examples": True,
            "token_based": False,
            "evaluation_type": "entity"

        }

        expected_scores = {
            "accuracy": 0.61,
            "precision": 0.68,
            "recall": 0.80,
            "f1_score": 0.73
        }

        response = self.client.post(self.url, payload, format="json")
        print_output(f"entity_evaluator:run_test_entity_evaluation_value_based:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        evaluator_id = response.data["id"]
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        task_object = evaluator_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output(f"entity_evaluator:run_test_entity_evaluation_value_based: waiting for evaluation task to finish, current status:", task_object.status)
            sleep(1)

        evaluator_json = evaluator_object.to_json()
        evaluator_json.pop("misclassified_examples")

        print_output(f"entity_evaluator:run_test_entity_evaluation_value_based:evaluator_object.json:", evaluator_json)

        for metric in choices.METRICS:
            self.assertEqual(round(evaluator_json[metric], 2), expected_scores[metric])

        self.assertEqual(evaluator_object.n_total_classes, 600)
        self.assertEqual(evaluator_object.n_true_classes, 437)
        self.assertEqual(evaluator_object.n_predicted_classes, 511)

        cm = np.array(json.loads(evaluator_object.confusion_matrix))
        cm_size = np.shape(cm)

        self.assertEqual(2, cm_size[0])
        self.assertEqual(2, cm_size[1])

        self.assertEqual(evaluator_object.document_count, 100)
        self.assertEqual(evaluator_object.add_individual_results, False)
        self.assertEqual(evaluator_object.scores_imprecise, False)
        self.assertEqual(evaluator_object.token_based, False)
        self.assertEqual(evaluator_object.evaluation_type, "entity")

        self.value_based_evaluator_id = evaluator_id

        self.add_cleanup_files(evaluator_id)


    def run_test_entity_evaluation_value_based_sent_index(self):
        """ Test value-based entity evaluation with sentence-level spans. """

        payload = {
            "description": "Test value-based entity evaluation with sentence-level spans",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name_sent_index,
            "predicted_fact": self.pred_fact_name_sent_index,
            "scroll_size": 50,
            "add_misclassified_examples": True,
            "token_based": False,
            "evaluation_type": "entity"

        }

        expected_scores = {
            "accuracy": 0.95,
            "precision": 0.92,
            "recall": 0.84,
            "f1_score": 0.88
        }

        response = self.client.post(self.url, payload, format="json")
        print_output(f"entity_evaluator:run_test_entity_evaluation_value_based_sent_index:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        evaluator_id = response.data["id"]
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        task_object = evaluator_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output(f"entity_evaluator:run_test_entity_evaluation_value_based_sent_index: waiting for evaluation task to finish, current status:", task_object.status)
            sleep(1)

        evaluator_json = evaluator_object.to_json()
        evaluator_json.pop("misclassified_examples")

        print_output(f"entity_evaluator:run_test_entity_evaluation_value_based_sent_index:evaluator_object.json:", evaluator_json)

        for metric in choices.METRICS:
            self.assertEqual(round(evaluator_json[metric], 2), expected_scores[metric])

        self.assertEqual(evaluator_object.n_total_classes, 481)
        self.assertEqual(evaluator_object.n_true_classes, 447)
        self.assertEqual(evaluator_object.n_predicted_classes, 410)

        cm = np.array(json.loads(evaluator_object.confusion_matrix))
        cm_size = np.shape(cm)

        self.assertEqual(2, cm_size[0])
        self.assertEqual(2, cm_size[1])

        self.assertEqual(evaluator_object.document_count, 100)
        self.assertEqual(evaluator_object.add_individual_results, False)
        self.assertEqual(evaluator_object.scores_imprecise, False)
        self.assertEqual(evaluator_object.token_based, False)
        self.assertEqual(evaluator_object.evaluation_type, "entity")

        self.value_based_sent_index_evaluator_id = evaluator_id

        self.add_cleanup_files(evaluator_id)


    def run_test_misclassified_examples_get(self, evaluator_id: int):
        """ Test misclassified_examples endpoint with GET request. """

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        token_based = evaluator_object.token_based

        url = f"{self.url}{evaluator_id}/misclassified_examples/"

        response = self.client.get(url, format="json")
        print_output(f"entity_evaluator:run_test_misclassified_examples_view_get:token_based:{token_based}:response.data:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        keys = ["substrings", "superstrings", "partial", "false_negatives", "false_positives"]

        for key in keys:
            self.assertTrue(key in response.data)
            self.assertTrue(isinstance(response.data[key], list))

        value_types_dict = ["substrings", "superstrings", "partial"]
        value_types_str = ["false_negatives", "false_positives"]

        for key in list(response.data.keys()):
            if response.data[key]:
                if key in value_types_dict:
                    self.assertTrue("true" in response.data[key][0]["value"])
                    self.assertTrue("pred" in response.data[key][0]["value"])
                elif key in value_types_str:
                    self.assertTrue(isinstance(response.data[key][0]["value"], str))
                self.assertTrue("count" in response.data[key][0])


    def run_test_misclassified_examples_post(self, evaluator_id: int):
        """ Test misclassified examples endpoint with POST request."""
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        token_based = evaluator_object.token_based

        url = f"{self.url}{evaluator_id}/misclassified_examples/"

        # Test param `min_count`
        payload_min_count = {
            "min_count": 2
        }

        response = self.client.post(url, payload_min_count, format="json")
        print_output(f"entity_evaluator:run_test_misclassified_examples_view_min_count_post:token_based:{token_based}:response.data:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        keys = ["substrings", "superstrings", "partial", "false_negatives", "false_positives"]

        for key in keys:
            self.assertTrue(key in response.data)
            self.assertTrue(isinstance(response.data[key], dict))
            nested_keys = ["values", "total_unique_count", "filtered_unique_count"]
            for nested_key in nested_keys:
                self.assertTrue(nested_key in response.data[key])

            # Check that the number of filtered values is smaller than or equal with the number of total values
            self.assertTrue(response.data[key]["total_unique_count"] >= response.data[key]["filtered_unique_count"])

            # Check that no value with smaller count than the min count is present in the results
            for value in response.data[key]["values"]:
                self.assertTrue(value["count"] >= payload_min_count["min_count"])

        # Test param `max_count`
        payload_max_count = {
            "max_count": 2
        }

        response = self.client.post(url, payload_max_count, format="json")
        print_output(f"entity_evaluator:run_test_misclassified_examples_view_max_count_post:token_based:{token_based}:response.data:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        keys = ["substrings", "superstrings", "partial", "false_negatives", "false_positives"]

        for key in keys:
            self.assertTrue(key in response.data)
            self.assertTrue(isinstance(response.data[key], dict))
            nested_keys = ["values", "total_unique_count", "filtered_unique_count"]
            for nested_key in nested_keys:
                self.assertTrue(nested_key in response.data[key])

            # Check that the number of filtered values is smaller than or equal with the number of total values
            self.assertTrue(response.data[key]["total_unique_count"] >= response.data[key]["filtered_unique_count"])

            # Check that no value with bigger count than max count is present in the results
            for value in response.data[key]["values"]:
                self.assertTrue(value["count"] <= payload_max_count["max_count"])

        # Test param `top_n`
        payload_top_n = {
            "top_n": 5
        }

        response = self.client.post(url, payload_top_n, format="json")
        print_output(f"entity_evaluator:run_test_misclassified_examples_view_top_n_post:token_based:{token_based}:response.data:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        keys = ["substrings", "superstrings", "partial", "false_negatives", "false_positives"]

        for key in keys:
            self.assertTrue(key in response.data)
            self.assertTrue(isinstance(response.data[key], dict))
            nested_keys = ["values", "total_unique_count", "filtered_unique_count"]
            for nested_key in nested_keys:
                self.assertTrue(nested_key in response.data[key])

            # Check that the number of filtered values is smaller than or equal with the number of total values
            self.assertTrue(response.data[key]["total_unique_count"] >= response.data[key]["filtered_unique_count"])

            # Check that at most top n values are present for each key
            self.assertTrue(response.data[key]["filtered_unique_count"] <= payload_top_n["top_n"])


    def run_test_entity_evaluation_with_query(self):
        """ Test if running the entity evaluation with query works. """

        payload = {
            "description": "Test evaluation with query",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name,
            "predicted_fact": self.pred_fact_name,
            "scroll_size": 50,
            "add_misclassified_examples": False,
            "query": self.test_query,
            "evaluation_type": "entity"
        }

        response = self.client.post(self.url, payload, format="json")
        print_output(f"entity_evaluator:run_test_entity_evaluation_with_query:response.data", response.data)

        evaluator_id = response.data["id"]
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)

        task_object = evaluator_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output(f"entity_evaluator:run_test_evaluation_with_query: waiting for evaluation task to finish, current status:", task_object.status)
            sleep(1)
            if task_object.status == Task.STATUS_FAILED:
                print_output(f"entity_evaluator:run_test_evaluation_with_query: status = failed: error:", task_object.errors)
            self.assertFalse(task_object.status == Task.STATUS_FAILED)

        # Check if the document count is in sync with the query
        self.assertEqual(evaluator_object.document_count, 68)
        self.add_cleanup_files(evaluator_id)


    def run_export_import(self, evaluator_id: int):
        """Tests endpoint for model export and import."""

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)

        eval_type = evaluator_object.evaluation_type

        # retrieve model zip
        url = f"{self.url}{evaluator_id}/export_model/"
        response = self.client.get(url)

        # Post model zip
        import_url = f"{self.url}import_model/"
        response = self.client.post(import_url, data={"file": BytesIO(response.content)})

        print_output(f"entity_evaluator:run_export_import:evaluation_type:{eval_type}:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        imported_evaluator_object = EvaluatorObject.objects.get(pk=response.data["id"])
        imported_evaluator_id = response.data["id"]

        # Check if the models and plot files exist.
        resources = imported_evaluator_object.get_resource_paths()
        for path in resources.values():
            file = pathlib.Path(path)
            self.assertTrue(file.exists())

        evaluator_object_json = evaluator_object.to_json()
        imported_evaluator_object_json = imported_evaluator_object.to_json()

        # Check if scores in original and imported model are the same
        for metric in choices.METRICS:
            self.assertEqual(evaluator_object_json[metric], imported_evaluator_object_json[metric])

        self.add_cleanup_files(evaluator_id)
        self.add_cleanup_files(imported_evaluator_id)


    def run_reevaluate(self, evaluator_id: int):
        """Tests endpoint for re-evaluation."""
        url = f"{self.url}{evaluator_id}/reevaluate/"
        payload = {}
        response = self.client.post(url, payload, format="json")
        print_output(f"entity_evaluator:run_reevaluate:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def run_delete(self, evaluator_id: int):
        """Test deleting evaluator and its resources."""

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        resources = evaluator_object.get_resource_paths()

        url = f"{self.url}{evaluator_id}/"
        response = self.client.delete(url, format="json")
        print_output(f"entity_evaluator:run_delete:delete:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url, format="json")
        print_output(f"entity_evaluator:run_delete:get:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Check if additional files get deleted
        for path in resources.values():
            file = pathlib.Path(path)
            self.assertFalse(file.exists())


    def run_patch(self, evaluator_id: int):
        """Test updating description."""
        url = f"{self.url}{evaluator_id}/"

        payload = {"description": "New description"}

        response = self.client.patch(url, payload, format="json")
        print_output(f"entity_evaluator:run_patch:response.data:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url, format="json")
        self.assertEqual(response.data["description"], "New description")

        self.add_cleanup_files(evaluator_id)
