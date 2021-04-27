import json
import os
import pathlib
import uuid
from io import BytesIO
from time import sleep

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_bert_tagger.tagger import BertTagger

from toolkit.bert_tagger.models import BertTagger as BertTaggerObject
from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.core import ElasticCore
from toolkit.helper_functions import download_bert_requirements, get_downloaded_bert_models, reindex_test_dataset
from toolkit.settings import ALLOW_BERT_MODEL_DOWNLOADS, BERT_CACHE_DIR, BERT_PRETRAINED_MODEL_DIRECTORY
from toolkit.test_settings import (TEST_BERT_MODEL, TEST_BERT_TAGGER_BINARY_CPU, TEST_BERT_TAGGER_BINARY_GPU, TEST_BERT_TAGGER_MULTICLASS_GPU, TEST_FACT_NAME, TEST_FIELD_CHOICE, TEST_KEEP_PLOT_FILES, TEST_QUERY, TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file, remove_folder


@override_settings(CELERY_ALWAYS_EAGER=True)
class BertTaggerObjectViewTests(APITransactionTestCase):
    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('BertTaggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("BertTaggerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/bert_taggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'

        self.test_tagger_id = None
        self.test_multiclass_tagger_id = None

        self.client.login(username='BertTaggerOwner', password='pw')

        # Check if TEST_BERT_MODEL is already downloaded
        available_models = get_downloaded_bert_models(BERT_PRETRAINED_MODEL_DIRECTORY)
        self.test_model_existed = True if TEST_BERT_MODEL in available_models else False
        download_bert_requirements(BERT_PRETRAINED_MODEL_DIRECTORY, [TEST_BERT_MODEL], cache_directory=BERT_CACHE_DIR, num_labels=2)

        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_BERT_TAGGER_NAME"
        self.new_multiclass_fact_name = "TEST_BERT_TAGGER_NAME_MC"
        self.new_fact_value = "TEST_BERT_TAGGER_VALUE"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_bert_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying taggers",
            "indices": [self.test_index_name],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": TEST_FIELD_CHOICE
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying bert tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])

        self.test_imported_binary_gpu_tagger_id = self.import_test_model(TEST_BERT_TAGGER_BINARY_GPU)
        self.test_imported_multiclass_gpu_tagger_id = self.import_test_model(TEST_BERT_TAGGER_MULTICLASS_GPU)

        self.test_imported_binary_cpu_tagger_id = self.import_test_model(TEST_BERT_TAGGER_BINARY_CPU)
        self.ec = ElasticCore()

    def import_test_model(self, file_path: str):
        """Import fine-tuned models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.url}import_model/'
        resp = self.client.post(import_url, data={'file': open(file_path, "rb")}).json()
        print_output("Importing test model:", resp)
        return resp["id"]


    def test(self):
        self.run_train_multiclass_bert_tagger_using_fact_name()
        self.run_train_balanced_multiclass_bert_tagger_using_fact_name()
        self.run_train_bert_tagger_using_query()
        self.run_bert_tag_text()
        self.run_bert_tag_with_imported_gpu_model()
        self.run_bert_tag_with_imported_cpu_model()
        self.run_bert_tag_random_doc()
        self.run_bert_epoch_reports_get()
        self.run_bert_epoch_reports_post()
        self.run_bert_get_available_models()
        self.run_bert_download_pretrained_model()
        self.run_bert_tag_and_feedback_and_retrain()
        self.run_bert_model_export_import()
        self.run_apply_binary_tagger_to_index()
        self.run_apply_multiclass_tagger_to_index()
        self.run_apply_tagger_to_index_invalid_input()

        self.add_cleanup_files(self.test_tagger_id)
        self.add_cleanup_folders()


    def tearDown(self) -> None:
        res = self.ec.delete_index(self.test_index_copy)
        self.ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete apply_bert_taggers test index {self.test_index_copy}", res)


    def add_cleanup_files(self, tagger_id: int):
        tagger_object = BertTaggerObject.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)


    def add_cleanup_folders(self):
        if not self.test_model_existed:
            test_model_dir = os.path.join(BERT_PRETRAINED_MODEL_DIRECTORY, BertTagger.normalize_name(TEST_BERT_MODEL))
            self.addCleanup(remove_folder, test_model_dir)


    def run_train_multiclass_bert_tagger_using_fact_name(self):
        """Tests BertTagger training with multiple classes and if a new Task gets created via the signal."""
        payload = {
            "description": "TestBertTaggerObjectTraining",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "indices": [{"name": self.test_index_name}],
            "maximum_sample_size": 500,
            "num_epochs": 2,
            "max_length": 15,
            "bert_model": TEST_BERT_MODEL
        }
        response = self.client.post(self.url, payload, format='json')

        print_output('test_create_multiclass_bert_tagger_training_and_task_signal:response.data', response.data)
        # Check if BertTagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Give the tagger some time to finish training
        sleep(5)
        tagger_id = response.data['id']
        self.test_multiclass_tagger_id = tagger_id
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_multiclass_bert_tagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))
        self.add_cleanup_files(tagger_id)


    def run_train_balanced_multiclass_bert_tagger_using_fact_name(self):
        """Tests balanced BertTagger training with multiple classes and if a new Task gets created via the signal."""
        payload = {
            "description": "TestBalancedBertTaggerObjectTraining",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "indices": [{"name": self.test_index_name}],
            "maximum_sample_size": 500,
            "num_epochs": 2,
            "max_length": 15,
            "bert_model": TEST_BERT_MODEL,
            "balance": True,
            "use_sentence_shuffle": True,
            "balance_to_max_limit": True
        }
        response = self.client.post(self.url, payload, format='json')

        print_output('test_create_balanced_multiclass_bert_tagger_training_and_task_signal:response.data', response.data)
        # Check if BertTagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Give the tagger some time to finish training
        sleep(5)
        tagger_id = response.data['id']
        self.test_multiclass_tagger_id = tagger_id
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_balanced_multiclass_bert_tagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))

        num_examples = json.loads(response.data["num_examples"])
        print_output('test_balanced_bert_tagger_num_examples_correct:num_examples', num_examples)
        for class_size in num_examples.values():
            self.assertTrue(class_size, payload["maximum_sample_size"])

        self.add_cleanup_files(tagger_id)


    def run_train_bert_tagger_using_query(self):
        """Tests BertTagger training, and if a new Task gets created via the signal."""
        payload = {
            "description": "TestBertTaggerTraining",
            "fields": TEST_FIELD_CHOICE,
            "query": json.dumps(TEST_QUERY),
            "maximum_sample_size": 500,
            "indices": [{"name": self.test_index_name}],
            "num_epochs": 2,
            "max_length": 15,
            "bert_model": TEST_BERT_MODEL
        }

        print_output(f"training tagger with payload: {payload}", 200)
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_binary_bert_tagger_training_and_task_signal:response.data', response.data)

        # Check if BertTagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Give the tagger some time to finish training
        sleep(5)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_binary_bert_tagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))

        # set trained tagger as active tagger
        self.test_tagger_id = tagger_id
        self.add_cleanup_files(tagger_id)


    def run_bert_tag_with_imported_gpu_model(self):
        """Test applying imported model trained on GPU."""
        payload = {
            "text": "mine kukele, loll"
        }
        response = self.client.post(f'{self.url}{self.test_imported_binary_gpu_tagger_id}/tag_text/', payload)
        print_output('test_bert_tagger_tag_with_imported_gpu_model:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("probability" in response.data)
        self.assertTrue("result" in response.data)
        self.assertTrue("tagger_id" in response.data)
        # Check if tagger learned to predict
        self.assertEqual("true", response.data["result"])

        self.add_cleanup_files(self.test_imported_binary_gpu_tagger_id)


    def run_bert_tag_with_imported_cpu_model(self):
        """Tests applying imported model trained on CPU."""
        payload = {
            "text": "mine kukele, loll"
        }
        response = self.client.post(f'{self.url}{self.test_imported_binary_cpu_tagger_id}/tag_text/', payload)
        print_output('test_bert_tagger_tag_with_imported_cpu_model:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("probability" in response.data)
        self.assertTrue("result" in response.data)
        self.assertTrue("tagger_id" in response.data)
        # Check if tagger learned to predict
        self.assertEqual("true", response.data["result"])

        self.add_cleanup_files(self.test_imported_binary_cpu_tagger_id)


    def run_bert_tag_text(self):
        """Tests tag prediction for texts."""
        payload = {
            "text": "mine kukele, loll"
        }
        response = self.client.post(f'{self.url}{self.test_tagger_id}/tag_text/', payload)
        print_output('test_bert_tagger_tag_text:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("probability" in response.data)
        self.assertTrue("result" in response.data)
        self.assertTrue("tagger_id" in response.data)


    def run_bert_tag_random_doc(self):
        """Tests the endpoint for the tag_random_doc action"""
        # Tag with specified fields
        payload = {
            "indices": [{"name": self.test_index_name}],
            "fields": TEST_FIELD_CHOICE
        }
        url = f'{self.url}{self.test_tagger_id}/tag_random_doc/'
        response = self.client.post(url, format="json", data=payload)
        print_output('test_bert_tagger_tag_random_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a dict
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue("prediction" in response.data)
        self.assertTrue("document" in response.data)
        self.assertTrue("probability" in response.data["prediction"])
        self.assertTrue("result" in response.data["prediction"])
        self.assertTrue("tagger_id" in response.data["prediction"])

        # Tag with unspecified fields
        payload = {
            "indices": [{"name": self.test_index_name}]
        }
        url = f'{self.url}{self.test_tagger_id}/tag_random_doc/'
        response = self.client.post(url, format="json", data=payload)
        print_output('test_bert_tagger_tag_random_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a dict
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue("prediction" in response.data)
        self.assertTrue("document" in response.data)
        self.assertTrue("probability" in response.data["prediction"])
        self.assertTrue("result" in response.data["prediction"])
        self.assertTrue("tagger_id" in response.data["prediction"])


    def run_bert_epoch_reports_get(self):
        """Tests endpoint for retrieving epoch reports via GET"""
        url = f'{self.url}{self.test_tagger_id}/epoch_reports/'
        response = self.client.get(url, format="json")
        print_output('test_bert_tagger_epoch_reports_get:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report is not empty
        self.assertTrue(len(response.data[0]) > 0)


    def run_bert_epoch_reports_post(self):
        """Tests endpoint for retrieving epoch reports via GET"""
        url = f'{self.url}{self.test_tagger_id}/epoch_reports/'
        payload_1 = {}
        payload_2 = {"ignore_fields": ["true_positive_rate", "false_positive_rate", "recall"]}

        response = self.client.post(url, format="json", data=payload_1)
        print_output('test_bert_tagger_epoch_reports_post_ignore_default:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report contains recall
        self.assertTrue("recall" in response.data[0])

        response = self.client.post(url, format="json", data=payload_2)
        print_output('test_bert_tagger_epoch_reports_post_ignore_custom:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is a list
        self.assertTrue(isinstance(response.data, list))
        # Check if first report does NOT contains recall
        self.assertTrue("recall" not in response.data[0])


    def run_bert_get_available_models(self):
        """Test endpoint for retrieving available BERT models."""
        url = f'{self.url}available_models/'
        response = self.client.get(url, format="json")
        print_output('test_bert_tagger_get_available_models:response.data', response.data)
        available_models = get_downloaded_bert_models(BERT_PRETRAINED_MODEL_DIRECTORY)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if the endpoint returns currently available models
        self.assertCountEqual(response.data, available_models)


    def run_bert_download_pretrained_model(self):
        """Test endpoint for downloading pretrained BERT model."""
        url = f'{self.url}download_pretrained_model/'
        # Test endpoint with valid payload
        valid_payload = {"bert_model": "prajjwal1/bert-tiny"}
        response = self.client.post(url, format="json", data=valid_payload)
        print_output('test_bert_tagger_download_pretrained_model_valid_input:response.data', response.data)
        if ALLOW_BERT_MODEL_DOWNLOADS:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        else:
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Test endpoint with invalid payload
        invalid_payload = {"bert_model": "foo"}
        response = self.client.post(url, format="json", data=invalid_payload)
        print_output('test_bert_tagger_download_pretrained_model_invalid_input:response.data', response.data)

        # The endpoint should throw and error
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_bert_model_export_import(self):
        """Tests endpoint for model export and import"""
        # test_tagger_id = self.test_tagger_id

        # retrieve model zip
        url = f'{self.url}{self.test_tagger_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_bert_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        bert_tagger = BertTaggerObject.objects.get(pk=response.data["id"])
        tagger_id = response.data['id']

        # Check if the models and plot files exist.
        resources = bert_tagger.get_resource_paths()
        for path in resources.values():
            file = pathlib.Path(path)
            self.assertTrue(file.exists())

        # Tests the endpoint for the tag_random_doc action"""
        url = f'{self.url}{bert_tagger.pk}/tag_random_doc/'
        random_doc_payload = {
            "indices": [{"name": self.test_index_name}],
            "fields": TEST_FIELD_CHOICE
        }
        response = self.client.post(url, data=random_doc_payload, format="json")
        print_output('test_bert_tag_random_doc_after_model_import:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        self.assertTrue('prediction' in response.data)
        # remove exported tagger files
        self.add_cleanup_files(tagger_id)


    def run_apply_binary_tagger_to_index(self):
        """Tests applying binary BERT tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_binary_bert_tagger_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        url = f'{self.url}{self.test_imported_binary_gpu_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply bert tagger to index test task",
            "new_fact_name": self.new_fact_name,
            "new_fact_value": self.new_fact_value,
            "indices": [{"name": self.test_index_copy}],
            "fields": TEST_FIELD_CHOICE
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_binary_bert_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = BertTaggerObject.objects.get(pk=self.test_imported_binary_gpu_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_binary_bert_tagger_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_binary_bert_tagger_to_index:elastic aggerator results:", results)

        # Check if the expected number of facts are added to the index
        expected_number_of_facts = 29
        self.assertTrue(results[self.new_fact_value] == expected_number_of_facts)

        self.add_cleanup_files(self.test_imported_binary_gpu_tagger_id)


    def run_apply_multiclass_tagger_to_index(self):
        """Tests applying multiclass BERT tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_multiclass_bert_tagger_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        url = f'{self.url}{self.test_imported_multiclass_gpu_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply bert tagger to index test task",
            "new_fact_name": self.new_multiclass_fact_name,
            "new_fact_value": self.new_fact_value,
            "indices": [{"name": self.test_index_copy}],
            "fields": TEST_FIELD_CHOICE
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_multiclass_bert_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = BertTaggerObject.objects.get(pk=self.test_imported_multiclass_gpu_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_multiclass_bert_tagger_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_multiclass_fact_name)
        print_output("test_apply_multiclass_bert_tagger_to_index:elastic aggerator results:", results)

        # Check if the expected facts and the expected number of them are added to the index
        expected_fact_value = "bar"
        expected_number_of_facts = 30
        self.assertTrue(expected_fact_value in results)
        self.assertTrue(results[expected_fact_value] == expected_number_of_facts)

        self.add_cleanup_files(self.test_imported_multiclass_gpu_tagger_id)


    def run_apply_tagger_to_index_invalid_input(self):
        """Tests applying multiclass BERT tagger to index using apply_to_index endpoint."""

        url = f'{self.url}{self.test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply bert tagger to index test task",
            "new_fact_name": self.new_fact_name,
            "new_fact_value": self.new_fact_value,
            "fields": "invalid_field_format",
            "bulk_size": 100,
            "query": json.dumps(TEST_QUERY)
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_invalid_apply_bert_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.add_cleanup_files(self.test_tagger_id)


    def run_bert_tag_and_feedback_and_retrain(self):
        """Tests feeback extra action."""

        payload = {
            "text": "This is some test text for the Tagger Test",
            "feedback_enabled": True
        }
        tag_text_url = f'{self.url}{self.test_tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_bert_tag_text_with_feedback:response.data', response.data)
        self.assertTrue('feedback' in response.data)

        # generate feedback
        fb_id = response.data['feedback']['id']
        feedback_url = f'{self.url}{self.test_tagger_id}/feedback/'
        payload = {"feedback_id": fb_id, "correct_result": "FUBAR"}
        response = self.client.post(feedback_url, payload, format='json')
        print_output('test_bert_tag_text_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)
        # list feedback
        feedback_list_url = f'{self.url}{self.test_tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_text_list_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue(len(response.data) > 0)

        # retrain model
        url = f'{self.url}{self.test_tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        print_output('test_bert_tagger_feedback:retrain', response.data)
        # test tagging again for this model
        payload = {"text": "This is some test text for the Tagger Test"}
        tag_text_url = f'{self.url}{self.test_tagger_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_bert_tagger_feedback_retrained_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)
        # delete feedback
        feedback_delete_url = f'{self.url}{self.test_tagger_id}/feedback/'
        response = self.client.delete(feedback_delete_url)
        print_output('test_bert_tagger_tag_doc_delete_feedback:response.data', response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)
        # list feedback again to make sure its emtpy
        feedback_list_url = f'{self.url}{self.test_tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_bert_tagger_tag_doc_list_feedback_after_delete:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) == 0)
        # remove created index
        feedback_index_url = f'{self.project_url}/feedback/'
        response = self.client.delete(feedback_index_url)
        print_output('test_bert_tagger_delete_feedback_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('success' in response.data)

        self.add_cleanup_files(self.test_tagger_id)
