import json
import pathlib
from io import BytesIO
from time import sleep
from typing import List

import numpy as np
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.core.task.models import Task
from texta_elastic.query import Query
from toolkit.evaluator import choices
from toolkit.evaluator.models import Evaluator as EvaluatorObject
from toolkit.helper_functions import reindex_test_dataset, set_core_setting
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
        self.fact_values_to_filter = ["650 bioeetika", "650 rahvusbibliograafiad"]
        self.test_query = Query()
        self.test_query.add_facts_filter(self.fact_names_to_filter, self.fact_values_to_filter, operator="must")
        self.test_query = self.test_query.__dict__()

        self.client.login(username="EvaluatorOwner", password="pw")


    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index=self.test_index, ignore=[400, 404])


    def test(self):

        self.run_test_invalid_fact_name()
        self.run_test_invalid_fact_value()
        self.run_test_invalid_average_function()

        self.run_test_evaluation_with_query()

        self.run_test_binary_evaluation()
        self.run_test_multilabel_evaluation(add_individual_results=True)
        self.run_test_multilabel_evaluation(add_individual_results=False)

        self.run_test_multilabel_evaluation_with_scoring_after_each_scroll(add_individual_results=True)
        self.run_test_multilabel_evaluation_with_scoring_after_each_scroll(add_individual_results=False)

        self.run_test_individual_results_enabled(self.memory_optimized_multilabel_evaluators.values())
        self.run_test_individual_results_enabled(self.multilabel_evaluators.values())
        self.run_test_individual_results_disabled(self.binary_evaluators.values())

        self.run_test_individual_results_view_multilabel(self.multilabel_evaluators["macro"])
        self.run_test_individual_results_view_invalid_input_multilabel(self.multilabel_evaluators["macro"])
        self.run_test_individual_results_view_binary(self.binary_evaluators["macro"])

        self.run_test_filtered_average_view_multilabel_get(self.multilabel_evaluators["macro"])
        self.run_test_filtered_average_view_multilabel_post(self.multilabel_evaluators["macro"])
        self.run_test_filtered_average_view_binary(self.binary_evaluators["macro"])

        self.run_export_import(self.binary_evaluators["macro"])
        self.run_export_import(self.multilabel_evaluators["macro"])

        self.run_patch(self.binary_evaluators["macro"])
        self.run_reevaluate(self.binary_evaluators["macro"])

        self.run_delete(self.binary_evaluators["macro"])


    def add_cleanup_files(self, evaluator_id: int):
        try:
            evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        except:
            pass
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, evaluator_object.plot.path)


    def run_patch(self, evaluator_id: int):
        """Test updating description."""
        url = f"{self.url}{evaluator_id}/"

        payload = {"description": "New description"}

        response = self.client.patch(url, payload, format="json")
        print_output(f"evaluator:run_patch:response.data:", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(url, format="json")
        self.assertEqual(response.data["description"], "New description")

        self.add_cleanup_files(evaluator_id)


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
        print_output(f"evaluator:run_test_individual_results_view_binary:avg:{evaluation_type}:default_payload:response.data:", response.data)

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
        print_output(f"evaluator:run_test_filtered_average_view_entity:avg:{evaluation_type}:default_payload:response.data:", response.data)

        # The usage of the endpoint is not available for binary evaluators
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        self.add_cleanup_files(evaluator_id)


    def run_test_entity_evaluation_token_based(self):
        """ Test entity evaluation. """

        main_payload = {
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
            "weighted": {"accuracy": 0.66, "precision": 0.68, "recall": 0.66, "f1_score": 0.67},
            "micro": {"accuracy": 0.66, "precision": 0.66, "recall": 0.66, "f1_score": 0.66},
            "macro": {"accuracy": 0.66, "precision": 0.49, "recall": 0.49, "f1_score": 0.49},
            "binary": {"accuracy": 0.66, "precision": 0.18, "recall": 0.21, "f1_score": 0.19}
        }

        for avg_function in self.binary_avg_functions:
            avg_function_payload = {"average_function": avg_function}
            payload = {**main_payload, **avg_function_payload}

            response = self.client.post(self.url, payload, format="json")
            print_output(f"evaluator:run_test_binary_evaluation:avg:{avg_function}:response.data", response.data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            evaluator_id = response.data["id"]
            evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
            while evaluator_object.task.status != Task.STATUS_COMPLETED:
                print_output(f"evaluator:run_test_binary_evaluation:avg:{avg_function}: waiting for evaluation task to finish, current status:", evaluator_object.task.status)
                sleep(1)

            evaluator_json = evaluator_object.to_json()
            evaluator_json.pop("individual_results")

            print_output(f"evaluator:run_test_binary_evaluation_avg_{avg_function}:evaluator_object.json:", evaluator_json)

            for metric in choices.METRICS:
                self.assertEqual(round(evaluator_json[metric], 2), expected_scores[avg_function][metric])

            self.assertEqual(evaluator_object.n_total_classes, 2)
            self.assertEqual(evaluator_object.n_true_classes, 2)
            self.assertEqual(evaluator_object.n_predicted_classes, 2)

            cm = np.array(json.loads(evaluator_object.confusion_matrix))
            cm_size = np.shape(cm)

            self.assertEqual(evaluator_object.n_total_classes, cm_size[0])
            self.assertEqual(evaluator_object.n_total_classes, cm_size[1])

            self.assertEqual(evaluator_object.document_count, 2000)
            self.assertEqual(evaluator_object.add_individual_results, payload["add_individual_results"])
            self.assertEqual(evaluator_object.scores_imprecise, False)
            self.assertEqual(evaluator_object.evaluation_type, "binary")

            self.assertEqual(evaluator_object.average_function, avg_function)

            self.binary_evaluators[avg_function] = evaluator_id

            self.add_cleanup_files(evaluator_id)


    def run_test_evaluation_with_query(self):
        """ Test if running the evaluation with query works. """
        payload = {
            "description": "Test evaluation with query",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name,
            "predicted_fact": self.pred_fact_name,
            "scroll_size": 500,
            "add_individual_results": False,
            "average_function": "macro",
            "query": json.dumps(self.test_query)
        }

        response = self.client.post(self.url, payload, format="json")
        print_output(f"evaluator:run_test_evaluation_with_query:avg:{payload['average_function']}:response.data", response.data)

        evaluator_id = response.data["id"]
        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)

        while evaluator_object.task.status != Task.STATUS_COMPLETED:
            print_output(f"evaluator:run_test_evaluation_with_query:avg:{payload['average_function']}: waiting for evaluation task to finish, current status:", evaluator_object.task.status)
            sleep(1)

        # Check if the document count is in sync with the query
        self.assertEqual(evaluator_object.document_count, 83)
        self.add_cleanup_files(evaluator_id)


    def run_test_multilabel_evaluation(self, add_individual_results: bool):
        """ Test multilabvel evaluation with averaging functions set in self.multilabel_avg_functions"""

        main_payload = {
            "description": "Test multilabel evaluation",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name,
            "predicted_fact": self.pred_fact_name,
            "scroll_size": 500,
            "add_individual_results": add_individual_results
        }

        expected_scores = {
            "weighted": {"accuracy": 0, "precision": 0.57, "recall": 0.67, "f1_score": 0.62},
            "micro": {"accuracy": 0, "precision": 0.57, "recall": 0.67, "f1_score": 0.62},
            "macro": {"accuracy": 0, "precision": 0.57, "recall": 0.67, "f1_score": 0.62},
            "samples": {"accuracy": 0, "precision": 0.55, "recall": 0.73, "f1_score": 0.61}
        }

        for avg_function in self.multilabel_avg_functions:
            avg_function_payload = {"average_function": avg_function}
            payload = {**main_payload, **avg_function_payload}

            response = self.client.post(self.url, payload, format="json")
            print_output(f"evaluator:run_test_multilabel_evaluation:avg:{avg_function}:response.data", response.data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            evaluator_id = response.data["id"]
            evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
            while evaluator_object.task.status != Task.STATUS_COMPLETED:
                print_output(f"evaluator:run_test_multilabel_evaluation:avg:{avg_function}: waiting for evaluation task to finish, current status:", evaluator_object.task.status)
                sleep(1)

            evaluator_json = evaluator_object.to_json()
            evaluator_json.pop("individual_results")

            print_output(f"evaluator:run_test_multilabel_evaluation:avg:{avg_function}:evaluator_object.json:", evaluator_json)
            for metric in choices.METRICS:
                self.assertEqual(round(evaluator_json[metric], 2), expected_scores[avg_function][metric])

            self.assertEqual(evaluator_object.n_total_classes, 10)
            self.assertEqual(evaluator_object.n_true_classes, 10)
            self.assertEqual(evaluator_object.n_predicted_classes, 10)

            cm = np.array(json.loads(evaluator_object.confusion_matrix))
            cm_size = np.shape(cm)

            self.assertEqual(evaluator_object.n_total_classes, cm_size[0])
            self.assertEqual(evaluator_object.n_total_classes, cm_size[1])

            self.assertEqual(evaluator_object.document_count, 2000)
            self.assertEqual(evaluator_object.add_individual_results, add_individual_results)
            self.assertEqual(evaluator_object.scores_imprecise, False)
            self.assertEqual(evaluator_object.evaluation_type, "multilabel")
            self.assertEqual(evaluator_object.average_function, avg_function)

            if add_individual_results:
                self.assertEqual(len(json.loads(evaluator_object.individual_results)), evaluator_object.n_total_classes)
                self.multilabel_evaluators[avg_function] = evaluator_id
            else:
                self.assertEqual(len(json.loads(evaluator_object.individual_results)), 0)

            self.add_cleanup_files(evaluator_id)


    def run_test_multilabel_evaluation_with_scoring_after_each_scroll(self, add_individual_results: bool):
        """
        Test multilabel evaluation with averaging functions set in self.multilabel_avg_functions and
        calculating and averaging scores after each scroll.
        """

        # Set required memory buffer high
        set_core_setting("TEXTA_EVALUATOR_MEMORY_BUFFER_GB", "100")

        main_payload = {
            "description": "Test Multilabel Evaluator",
            "indices": [{"name": self.test_index}],
            "true_fact": self.true_fact_name,
            "predicted_fact": self.pred_fact_name,
            "scroll_size": 500,
            "add_individual_results": add_individual_results,

        }

        for avg_function in self.multilabel_avg_functions:
            avg_function_payload = {"average_function": avg_function}
            payload = {**main_payload, **avg_function_payload}

            response = self.client.post(self.url, payload, format="json")
            print_output(f"evaluator:run_test_multilabel_evaluation_with_scoring_after_each_scroll:avg:{avg_function}:response.data", response.data)

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

            evaluator_id = response.data["id"]
            evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
            while evaluator_object.task.status != Task.STATUS_COMPLETED:
                print_output(f"evaluator:run_test_multilabel_evaluation_with_scoring_after_each_scroll:avg:{avg_function}: waiting for evaluation task to finish, current status:", evaluator_object.task.status)
                sleep(1)

            evaluator_json = evaluator_object.to_json()
            evaluator_json.pop("individual_results")

            print_output(f"evaluator:run_test_multilabel_evaluation_with_scoring_after_each_scroll:avg:{avg_function}:evaluator_object.json:", evaluator_json)
            for metric in choices.METRICS:
                if metric == "accuracy":
                    self.assertEqual(evaluator_json[metric], 0)
                else:
                    self.assertTrue(0.5 <= evaluator_json[metric] <= 0.8)

            self.assertEqual(evaluator_object.n_total_classes, 10)
            self.assertEqual(evaluator_object.n_true_classes, 10)
            self.assertEqual(evaluator_object.n_predicted_classes, 10)

            cm = np.array(json.loads(evaluator_object.confusion_matrix))
            cm_size = np.shape(cm)

            self.assertEqual(evaluator_object.n_total_classes, cm_size[0])
            self.assertEqual(evaluator_object.n_total_classes, cm_size[1])

            scores_imprecise = True if avg_function != "micro" else False

            self.assertEqual(evaluator_object.document_count, 2000)
            self.assertEqual(evaluator_object.add_individual_results, add_individual_results)
            self.assertEqual(evaluator_object.scores_imprecise, scores_imprecise)
            self.assertEqual(evaluator_object.evaluation_type, "multilabel")
            self.assertEqual(evaluator_object.average_function, avg_function)

            if add_individual_results:
                self.assertEqual(len(json.loads(evaluator_object.individual_results)), evaluator_object.n_total_classes)
                self.memory_optimized_multilabel_evaluators[avg_function] = evaluator_id
            else:
                self.assertEqual(len(json.loads(evaluator_object.individual_results)), 0)

            self.add_cleanup_files(evaluator_id)

        # Set memory buffer back to default
        set_core_setting("TEXTA_EVALUATOR_MEMORY_BUFFER_GB", "")


    def run_export_import(self, evaluator_id: int):
        """Tests endpoint for model export and import."""

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)

        eval_type = evaluator_object.evaluation_type
        avg_function = evaluator_object.average_function

        # retrieve model zip
        url = f"{self.url}{evaluator_id}/export_model/"
        response = self.client.get(url)

        # Post model zip
        import_url = f"{self.url}import_model/"
        response = self.client.post(import_url, data={"file": BytesIO(response.content)})

        print_output(f"evaluator:run_export_import:avg:{avg_function}:evaluation_type:{eval_type}:response.data", response.data)

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

        # Check that the sizes of individual labels are the same
        self.assertEqual(len(json.loads(evaluator_object.individual_results)), len(json.loads(imported_evaluator_object.individual_results)))

        self.add_cleanup_files(evaluator_id)
        self.add_cleanup_files(imported_evaluator_id)


    def run_reevaluate(self, evaluator_id: int):
        """Tests endpoint for re-evaluation."""
        url = f"{self.url}{evaluator_id}/reevaluate/"
        payload = {}
        response = self.client.post(url, payload, format="json")
        print_output(f"evaluator:run_reevaluate:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def run_delete(self, evaluator_id: int):
        """Test deleting evaluator and its resources."""

        evaluator_object = EvaluatorObject.objects.get(pk=evaluator_id)
        resources = evaluator_object.get_resource_paths()

        url = f"{self.url}{evaluator_id}/"
        response = self.client.delete(url, format="json")
        print_output(f"evaluator:run_delete:delete:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        response = self.client.get(url, format="json")
        print_output(f"evaluator:run_delete:get:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Check if additional files get deleted
        for path in resources.values():
            file = pathlib.Path(path)
            self.assertFalse(file.exists())
