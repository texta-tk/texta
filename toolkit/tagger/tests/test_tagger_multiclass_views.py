import json
import uuid
from time import sleep
from typing import List

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.helper_functions import reindex_test_dataset
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (
    TEST_BIN_FACT_QUERY,
    TEST_EMPTY_QUERY,
    TEST_FACT_NAME,
    TEST_FIELD,
    TEST_FIELD_CHOICE,
    TEST_KEEP_PLOT_FILES,
    TEST_POS_LABEL,
    TEST_QUERY,
    TEST_TAGGER_MULTICLASS,
    TEST_VERSION_PREFIX
)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerViewTests(APITransactionTestCase):


    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.multitag_text_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/multitag_text/'

        # set vectorizer & classifier options
        self.vectorizer_opts = ('TfIdf Vectorizer',)
        self.classifier_opts = ('Logistic Regression',)

        # list tagger_ids for testing. is populated during training test
        self.test_tagger_ids = []
        self.client.login(username='taggerOwner', password='pw')

        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_MULTICLASS_TAGGER_NAME"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_multiclass_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying multiclass taggers",
            "indices": [self.test_index_name],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying multiclass tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])

        self.test_imported_multiclass_tagger_id = self.import_test_model(TEST_TAGGER_MULTICLASS)


    def import_test_model(self, file_path: str):
        """Import models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.url}import_model/'
        resp = self.client.post(import_url, data={'file': open(file_path, "rb")}).json()
        print_output("Importing test model:", resp)
        return resp["id"]


    def test_run(self):
        self.run_create_multiclass_tagger_training_and_task_signal()
        self.run_create_balanced_multiclass_tagger_training_and_task_signal()
        self.run_create_multiclass_tagger_with_insufficient_number_of_examples()
        self.run_create_binary_multiclass_tagger_training_and_task_signal()
        self.run_create_binary_multiclass_tagger_training_and_task_signal_invalid_payload()
        self.run_multiclass_tag_text(self.test_tagger_ids)
        self.run_apply_multiclass_tagger_to_index()
        self.run_apply_mutliclass_tagger_to_index_invalid_input()


    def add_cleanup_files(self, tagger_id):
        tagger_object = Tagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)
        if tagger_object.embedding:
            self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)


    def tearDown(self) -> None:
        Tagger.objects.all().delete()
        ec = ElasticCore()
        res = ec.delete_index(self.test_index_copy)
        ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete apply_multiclass_taggers test index {self.test_index_copy}", res)


    def run_create_multiclass_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger, and if a new Task gets created via the signal"""
        # run test for multiclass training
        # run test for each vectorizer & classifier option
        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                payload = {
                    "description": "TestTaggerMultiClass",
                    "fields": TEST_FIELD_CHOICE,
                    "fact_name": TEST_FACT_NAME,
                    "query": json.dumps(TEST_EMPTY_QUERY),
                    "vectorizer": vectorizer_opt,
                    "classifier": classifier_opt,
                    "maximum_sample_size": 500,
                    "negative_multiplier": 1.0,
                    "score_threshold": 0.1
                }
                # as lemmatization is slow, do it only once
                lemmatize = False
                # procees to analyze result
                response = self.client.post(self.url, payload, format='json')
                print_output('test_create_multiclass_tagger_training_and_task_signal:response.data', response.data)
                # Check if Tagger gets created
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                created_tagger = Tagger.objects.get(id=response.data['id'])
                # add tagger to be tested
                self.test_tagger_ids.append(created_tagger.pk)
                # Check if not errors
                task_object = created_tagger.tasks.last()
                self.assertEqual(task_object.errors, '[]')
                # Remove tagger files after test is done
                self.add_cleanup_files(created_tagger.id)
                # Check if Task gets created via a signal
                self.assertTrue(task_object is not None)
                # Check if Tagger gets trained and completed
                self.assertEqual(task_object.status, Task.STATUS_COMPLETED)
                # Check if Tagger object contains classes
                self.assertTrue(isinstance(response.data["classes"], list))
                self.assertTrue(len(response.data["classes"]) >= 2)


    def run_create_multiclass_tagger_with_insufficient_number_of_examples(self):
        """Tests the endpoint for a new multiclass Tagger with insufficient number of examples."""
        # run test for multiclass training
        # run test for each vectorizer & classifier option
        vectorizer_opt = self.vectorizer_opts[0]
        classifier_opt = self.classifier_opts[0]

        # Pos label is undefined by the user
        invalid_payload = {
            "description": "TestBinaryTaggerMultiClass",
            "fields": TEST_FIELD_CHOICE,
            "fact_name": TEST_FACT_NAME,
            "query": json.dumps(TEST_EMPTY_QUERY),
            "vectorizer": vectorizer_opt,
            "classifier": classifier_opt,
            "maximum_sample_size": 2000,
            "minimum_sample_size": 1000,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
        }

        response = self.client.post(self.url, invalid_payload, format='json')
        print_output('test_create_multiclass_tagger_with_insufficient_number_of_examples:response.data', response.data)
        # Check if creating the Tagger fails with status code 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_create_binary_multiclass_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new binary multiclass Tagger, and if a new Task gets created via the signal"""
        # run test for multiclass training
        # run test for each vectorizer & classifier option
        vectorizer_opt = self.vectorizer_opts[0]
        classifier_opt = self.classifier_opts[0]
        payload = {
            "description": "TestBinaryTaggerMultiClass",
            "fields": TEST_FIELD_CHOICE,
            "fact_name": TEST_FACT_NAME,
            "query": json.dumps(TEST_BIN_FACT_QUERY),
            "vectorizer": vectorizer_opt,
            "classifier": classifier_opt,
            "maximum_sample_size": 150,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "pos_label": TEST_POS_LABEL,
        }
        # procees to analyze result
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_binary_multiclass_tagger_training_and_task_signal:response.data', response.data)
        # Check if Tagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_tagger = Tagger.objects.get(id=response.data['id'])

        # Check if not errors
        task_object = created_tagger.tasks.last()
        self.assertEqual(task_object.errors, '[]')
        # Remove tagger files after test is done
        self.add_cleanup_files(created_tagger.id)
        # Check if Task gets created via a signal
        self.assertTrue(task_object is not None)
        # Check if Tagger gets trained and completed
        self.assertEqual(task_object.status, Task.STATUS_COMPLETED)

        # Test if each class has correct number of examples
        num_examples = json.loads(created_tagger.num_examples)
        print_output('test_balanced_tagger_num_examples_correct:num_examples', num_examples)
        for class_size in num_examples.values():
            self.assertTrue(class_size, payload["maximum_sample_size"])


    def run_create_binary_multiclass_tagger_training_and_task_signal_invalid_payload(self):
        """Tests the endpoint for a new binary multiclass Tagger with invalid payload."""
        # run test for multiclass training
        # run test for each vectorizer & classifier option
        vectorizer_opt = self.vectorizer_opts[0]
        classifier_opt = self.classifier_opts[0]

        # Pos label is undefined by the user
        invalid_payload_1 = {
            "description": "TestBinaryTaggerMultiClassMissingPosLabel",
            "fields": TEST_FIELD_CHOICE,
            "fact_name": TEST_FACT_NAME,
            "query": json.dumps(TEST_BIN_FACT_QUERY),
            "vectorizer": vectorizer_opt,
            "classifier": classifier_opt,
            "maximum_sample_size": 150,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
        }

        response = self.client.post(self.url, invalid_payload_1, format='json')
        print_output('test_create_binary_multiclass_tagger_training_and_task_signal_missing_pos_label:response.data', response.data)
        # Check if creating the Tagger fails with status code 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # The inserted pos label is not present in the data
        invalid_payload_2 = {
            "description": "TestBinaryTaggerMultiClassIncorrectPosLabel",
            "fields": TEST_FIELD_CHOICE,
            "fact_name": TEST_FACT_NAME,
            "query": json.dumps(TEST_BIN_FACT_QUERY),
            "vectorizer": vectorizer_opt,
            "classifier": classifier_opt,
            "maximum_sample_size": 150,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "pos_label": "invalid_fact_val"
        }
        # procees to analyze result
        response = self.client.post(self.url, invalid_payload_2, format='json')
        print_output('test_create_binary_multiclass_tagger_training_and_task_signal_invalid_pos_label:response.data', response.data)
        # Check if creating the Tagger fails with status code 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_create_balanced_multiclass_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new balanced multiclass Tagger, and if a new Task gets created via the signal"""
        # run test for multiclass training
        # run test for each vectorizer & classifier option
        vectorizer_opt = self.vectorizer_opts[0]
        classifier_opt = self.classifier_opts[0]
        payload = {
            "description": "TestBalancedTaggerMultiClass",
            "fields": TEST_FIELD_CHOICE,
            "fact_name": TEST_FACT_NAME,
            "query": json.dumps(TEST_EMPTY_QUERY),
            "vectorizer": vectorizer_opt,
            "classifier": classifier_opt,
            "maximum_sample_size": 150,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "balance": True,
            "balance_to_max_limit": True
        }
        # as lemmatization is slow, do it only once
        lemmatize = False
        # procees to analyze result
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_balanced_multiclass_tagger_training_and_task_signal:response.data', response.data)
        # Check if Tagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_tagger = Tagger.objects.get(id=response.data['id'])

        # Check if not errors
        task_object = created_tagger.tasks.last()
        self.assertEqual(task_object.errors, '[]')
        # Remove tagger files after test is done
        self.add_cleanup_files(created_tagger.id)
        # Check if Task gets created via a signal
        self.assertTrue(task_object is not None)
        # Check if Tagger gets trained and completed
        self.assertEqual(task_object.status, Task.STATUS_COMPLETED)

        # Test if each class has correct number of examples
        num_examples = json.loads(created_tagger.num_examples)
        print_output('test_balanced_tagger_num_examples_correct:num_examples', num_examples)
        for class_size in num_examples.values():
            self.assertTrue(class_size, payload["maximum_sample_size"])


    def run_multiclass_tag_text(self, test_tagger_ids: List[int]):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "This is some test text for the Tagger Test"}
        for test_tagger_id in test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_multiclass_tag_text:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('result' in response.data)
            self.assertTrue('probability' in response.data)


    def run_apply_multiclass_tagger_to_index(self):
        """Tests applying multiclass tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        task_object = self.reindexer_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_multiclass_tagger_to_index: waiting for reindexer task to finish, current status:', task_object.status)
            sleep(2)

        test_tagger_id = self.test_imported_multiclass_tagger_id
        url = f'{self.url}{test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply multiclass tagger test task",
            "new_fact_name": self.new_fact_name,
            "indices": [{"name": self.test_index_copy}],
            "fields": TEST_FIELD_CHOICE,
            "lemmatize": False
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_multiclass_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = Tagger.objects.get(pk=test_tagger_id)

        # Wait til the task has finished
        task_object = tagger_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_mutliclass_tagger_to_index: waiting for applying tagger task to finish, current status:', task_object.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_multiclass_tagger_to_index:elastic aggerator results:", results)

        # Check if applying the tagger results in at least 1 new fact
        self.assertTrue(len(results) >= 1)

        fact_value_1 = "bar"
        fact_value_2 = "foo"

        n_fact_value_1 = 18
        n_fact_value_2 = 12

        # Check if expected number of new facts is added to the index
        self.assertTrue(fact_value_1 in results)
        self.assertTrue(fact_value_2 in results)
        self.assertTrue(results[fact_value_1] == n_fact_value_1)
        self.assertTrue(results[fact_value_2] == n_fact_value_2)

        self.add_cleanup_files(test_tagger_id)


    def run_apply_mutliclass_tagger_to_index_invalid_input(self):
        """Tests applying multiclass tagger to index using apply_to_index endpoint with invalid input."""

        test_tagger_id = self.test_tagger_ids[0]
        url = f'{self.url}{test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "fields": "invalid_field_format",
            "lemmatize": False,
            "bulk_size": 100
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_to_index_invalid_input:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
