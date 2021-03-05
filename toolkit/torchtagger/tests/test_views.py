import pathlib
import uuid
import json
from io import BytesIO
from time import sleep

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.elastic.reindexer.models import Reindexer
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.core import ElasticCore

from toolkit.core.task.models import Task

from toolkit.test_settings import (
    TEST_FACT_NAME,
    TEST_FIELD_CHOICE,
    TEST_INDEX,
    TEST_VERSION_PREFIX,
    TEST_KEEP_PLOT_FILES,
    TEST_QUERY,
    TEST_TORCH_TAGGER_BINARY,
    TEST_TORCH_TAGGER_MULTICLASS
    )
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file
from toolkit.torchtagger.models import TorchTagger
from toolkit.torchtagger.torch_models.models import TORCH_MODELS


@override_settings(CELERY_ALWAYS_EAGER=True)
class TorchTaggerViewTests(APITransactionTestCase):
    def setUp(self):
        # Owner of the project
        self.user = create_test_user('torchTaggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("torchTaggerTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/torchtaggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.test_embedding_id = None
        self.torch_models = list(TORCH_MODELS.keys())
        self.test_tagger_id = None
        self.test_multiclass_tagger_id = None

        self.client.login(username='torchTaggerOwner', password='pw')

        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_TORCH_TAGGER_NAME"
        self.new_multiclass_fact_name = "TEST_TORCH_TAGGER_NAME_MC"
        self.new_fact_value = "TEST_TORCH_TAGGER_VALUE"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_torch_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying taggers",
            "indices": [TEST_INDEX],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": TEST_FIELD_CHOICE
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying torch tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])

        self.test_imported_binary_tagger_id = self.import_test_model(TEST_TORCH_TAGGER_BINARY)
        self.test_imported_multiclass_tagger_id = self.import_test_model(TEST_TORCH_TAGGER_MULTICLASS)


    def import_test_model(self, file_path: str):
        """Import models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.url}import_model/'
        resp = self.client.post(import_url, data={'file': open(file_path, "rb")}).json()
        print_output("Importing test model:", resp)
        return resp["id"]


    def tearDown(self) -> None:
        res = ElasticCore().delete_index(self.test_index_copy)
        print_output(f"Delete apply_torch_taggers test index {self.test_index_copy}", res)


    def test(self):
        self.run_train_embedding()
        self.run_train_tagger_using_query()
        self.run_train_multiclass_tagger_using_fact_name()
        self.run_tag_text()
        self.run_tag_random_doc()
        self.run_epoch_reports_get()
        self.run_epoch_reports_post()
        self.run_tag_and_feedback_and_retrain()
        self.run_model_export_import()
        self.run_apply_binary_tagger_to_index()
        self.run_apply_multiclass_tagger_to_index()
        self.run_apply_tagger_to_index_invalid_input()


    def add_cleanup_files(self, tagger_id):
        tagger_object = TorchTagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)
        self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)


    def run_train_embedding(self):
        # payload for training embedding
        payload = {
            "description": "TestEmbedding",
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 300
        }
        # post
        embeddings_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, payload, format='json')
        self.test_embedding_id = response.data["id"]
        print_output("run_train_embedding", 201)


    def run_train_tagger_using_query(self):
        """Tests TorchTagger training, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestTorchTaggerTraining",
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3,
            "embedding": self.test_embedding_id,
        }

        print_output(f"training tagger with payload: {payload}", 200)
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_binary_torchtagger_training_and_task_signal:response.data', response.data)

        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check if f1 not NULL (train and validation success)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_torchtagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))
        self.test_tagger_id = tagger_id
        # add cleanup
        self.add_cleanup_files(tagger_id)


    def run_train_multiclass_tagger_using_fact_name(self):
        """Tests TorchTagger training with multiple classes and if a new Task gets created via the signal"""
        payload = {
            "description": "TestTorchTaggerTraining",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3,
            "embedding": self.test_embedding_id,
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_multiclass_torchtagger_training_and_task_signal:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check if f1 not NULL (train and validation success)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_torchtagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))
        self.test_multiclass_tagger_id = tagger_id
        # add cleanup
        self.add_cleanup_files(tagger_id)


    def run_tag_text(self):
        """Tests tag prediction for texts."""
        payload = {
            "text": "mine kukele, kala"
        }
        response = self.client.post(f'{self.url}{self.test_tagger_id}/tag_text/', payload)
        print_output('test_torchtagger_tag_text:response.data', response.data)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)
        self.assertTrue('tagger_id' in response.data)


    def run_tag_random_doc(self):
        """Tests the endpoint for the tag_random_doc action"""
        payload = {
            "indices": [{"name": TEST_INDEX}]
        }
        url = f'{self.url}{self.test_tagger_id}/tag_random_doc/'
        response = self.client.post(url, format="json", data=payload)
        print_output('test_tag_random_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('prediction' in response.data)
        self.assertTrue('result' in response.data['prediction'])
        self.assertTrue('probability' in response.data['prediction'])
        self.assertTrue('tagger_id' in response.data['prediction'])


    def run_epoch_reports_get(self):
        """Tests endpoint for retrieving epoch reports via GET"""
        url = f'{self.url}{self.test_tagger_id}/epoch_reports/'
        response = self.client.get(url, format="json")
        print_output('test_torchagger_epoch_reports_get:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report is not empty
        self.assertTrue(len(response.data[0])>0)


    def run_epoch_reports_post(self):
        """Tests endpoint for retrieving epoch reports via GET"""
        url = f'{self.url}{self.test_tagger_id}/epoch_reports/'
        payload_1 = {}
        payload_2 = {"ignore_fields": ["true_positive_rate", "false_positive_rate", "recall"]}

        response = self.client.post(url, format="json", data=payload_1)
        print_output('test_torchagger_epoch_reports_post_ignore_default:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report contains recall
        self.assertTrue("recall" in response.data[0])

        response = self.client.post(url, format="json", data=payload_2)
        print_output('test_torchtagger_epoch_reports_post_ignore_custom:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report does NOT contains recall
        self.assertTrue("recall" not in response.data[0])


    def run_model_export_import(self):
        """Tests endpoint for model export and import"""
        test_tagger_group_id = self.test_tagger_id

        # retrieve model zip
        url = f'{self.url}{test_tagger_group_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        tagger_id = response.data['id']
        print_output('test_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        torchtagger = TorchTagger.objects.get(pk=response.data["id"])

        # Check if the models and plot files exist.
        resources = torchtagger.get_resource_paths()
        for path in resources.values():
            file = pathlib.Path(path)
            self.assertTrue(file.exists())

        # Tests the endpoint for the tag_random_doc action"""
        url = f'{self.url}{torchtagger.pk}/tag_random_doc/'
        payload = {
            "indices": [{"name": TEST_INDEX}]
        }
        response = self.client.post(url, format='json', data=payload)
        print_output('test_torchtagger_tag_random_doc_after_import:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        self.assertTrue('prediction' in response.data)
        self.assertTrue('result' in response.data['prediction'])
        self.assertTrue('probability' in response.data['prediction'])
        self.assertTrue('tagger_id' in response.data['prediction'])
        self.add_cleanup_files(tagger_id)


    def run_apply_binary_tagger_to_index(self):
        """Tests applying binary torch tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_binary_torch_tagger_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        url = f'{self.url}{self.test_imported_binary_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply torch tagger to index test task",
            "new_fact_name": self.new_fact_name,
            "new_fact_value": self.new_fact_value,
            "indices": [{"name": self.test_index_copy}],
            "fields": TEST_FIELD_CHOICE
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_binary_torch_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = TorchTagger.objects.get(pk=self.test_imported_binary_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_binary_torch_tagger_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_binary_torch_tagger_to_index:elastic aggerator results:", results)

        # Check if expected number of facts is added
        self.assertTrue(results[self.new_fact_value] == 30)
        
        self.add_cleanup_files(self.test_imported_binary_tagger_id)


    def run_apply_multiclass_tagger_to_index(self):
        """Tests applying multiclass torch tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_multiclass_torch_tagger_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        url = f'{self.url}{self.test_imported_multiclass_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply torch tagger to index test task",
            "new_fact_name": self.new_multiclass_fact_name,
            "new_fact_value": self.new_fact_value,
            "indices": [{"name": self.test_index_copy}],
            "fields": TEST_FIELD_CHOICE
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_multiclass_torch_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = TorchTagger.objects.get(pk=self.test_imported_multiclass_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_multiclass_torch_tagger_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_multiclass_fact_name)
        print_output("test_apply_multiclass_torch_tagger_to_index:elastic aggerator results:", results)

        # Check if the expected facts with expected number of values is added
        expected_fact_value = "foo"
        expected_number_of_facts = 30
        self.assertTrue(expected_fact_value in results)
        self.assertTrue(results[expected_fact_value] == expected_number_of_facts )

        self.add_cleanup_files(self.test_imported_multiclass_tagger_id)


    def run_apply_tagger_to_index_invalid_input(self):
        """Tests applying multiclass torch tagger to index using apply_to_index endpoint."""

        url = f'{self.url}{self.test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply torch tagger to index test task",
            "new_fact_name": self.new_fact_name,
            "new_fact_value": self.new_fact_value,
            "fields": "invalid_field_format"
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_invalid_apply_torch_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.add_cleanup_files(self.test_tagger_id)


    def run_tag_and_feedback_and_retrain(self):
        """Tests feeback extra action."""
        tagger_id = self.test_tagger_id
        payload = {
            "text": "This is some test text for the Tagger Test",
            "feedback_enabled": True
        }
        tag_text_url = f'{self.url}{tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_text_with_feedback:response.data', response.data)
        self.assertTrue('feedback' in response.data)

        # generate feedback
        fb_id = response.data['feedback']['id']
        feedback_url = f'{self.url}{tagger_id}/feedback/'
        payload = {"feedback_id": fb_id, "correct_result": "FUBAR"}
        response = self.client.post(feedback_url, payload, format='json')
        print_output('test_tag_text_with_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)
        # list feedback
        feedback_list_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_text_list_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue(len(response.data) > 0)

        # add model files before retraining
        self.add_cleanup_files(tagger_id)

        # retrain model
        url = f'{self.url}{tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        print_output('test_feedback:retrain', response.data)
        # test tagging again for this model
        payload = {"text": "This is some test text for the Tagger Test"}
        tag_text_url = f'{self.url}{tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_feedback_retrained_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)
        # delete feedback
        feedback_delete_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.delete(feedback_delete_url)
        print_output('test_tag_doc_delete_feedback:response.data', response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)
        # list feedback again to make sure its emtpy
        feedback_list_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_doc_list_feedback_after_delete:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) == 0)
        # remove created index
        feedback_index_url = f'{self.project_url}/feedback/'
        response = self.client.delete(feedback_index_url)
        print_output('test_delete_feedback_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('success' in response.data)

        # add model files after retraining
        self.add_cleanup_files(tagger_id)
