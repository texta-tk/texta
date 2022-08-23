import json
import pathlib
import uuid
from io import BytesIO
from time import sleep

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore
from texta_torch_tagger.tagger import TORCH_MODELS

from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import (
    TEST_BIN_FACT_QUERY,
    TEST_FACT_NAME,
    TEST_FIELD_CHOICE,
    TEST_KEEP_PLOT_FILES,
    TEST_POS_LABEL,
    TEST_QUERY,
    TEST_VERSION_PREFIX
)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file
from toolkit.torchtagger.models import TorchTagger


@override_settings(CELERY_ALWAYS_EAGER=True)
class TorchTaggerViewTests(APITransactionTestCase):
    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('torchTaggerOwner', 'my@email.com', 'pw')
        self.project = project_creation('torchTaggerTestProject', self.test_index_name, self.user)
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
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_torch_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying taggers",
            "indices": [self.test_index_name],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": TEST_FIELD_CHOICE
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying torch tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])
        self.ec = ElasticCore()


    def import_test_model(self, file_path: str):
        """Import models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.url}import_model/'
        resp = self.client.post(import_url, data={'file': open(file_path, "rb")}).json()
        print_output("Importing test model:", resp)
        return resp["id"]


    def tearDown(self) -> None:
        res = self.ec.delete_index(self.test_index_copy)
        self.ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete apply_torch_taggers test index {self.test_index_copy}", res)


    def test(self):
        pass
        # self.run_train_embedding()
        # self.run_train_tagger_using_query()
        # self.run_train_torchtagger_without_embedding()
        # self.run_train_multiclass_tagger_using_fact_name()
        # self.run_train_balanced_multiclass_tagger_using_fact_name()
        # self.run_train_binary_multiclass_tagger_using_fact_name()
        # self.run_train_binary_multiclass_tagger_using_fact_name_invalid_payload()
        # self.run_tag_text()
        # self.run_model_export_import()
        # self.run_tag_with_imported_gpu_model() # were already commented out
        # self.run_tag_with_imported_cpu_model() # were already commented out
        # self.run_tag_random_doc()
        # self.run_epoch_reports_get()
        # self.run_epoch_reports_post()
        # self.run_tag_and_feedback_and_retrain()
        # self.run_apply_binary_tagger_to_index()
        # self.run_apply_tagger_to_index_invalid_input()


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


    def run_train_torchtagger_without_embedding(self):
        payload = {
            "description": "TestTorchTaggerTraining",
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3}

        response = self.client.post(self.url, payload, format='json')
        print_output(f"run_train_torchtagger_without_embedding", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def run_train_tagger_using_query(self):
        """Tests TorchTagger training, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestTorchTaggerTraining",
            "fields": TEST_FIELD_CHOICE,
            "query": json.dumps(TEST_QUERY),
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

        print_output('test_torchtagger_has_classes:response.data.classes', response.data["classes"])
        self.assertTrue(isinstance(response.data["classes"], list))
        self.assertTrue(len(response.data["classes"]) == 2)

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

        print_output('test_torchtagger_has_classes:response.data.classes', response.data["classes"])
        self.assertTrue(isinstance(response.data["classes"], list))
        self.assertTrue(len(response.data["classes"]) > 2)

        self.test_multiclass_tagger_id = tagger_id
        # add cleanup
        self.add_cleanup_files(tagger_id)


    def run_train_binary_multiclass_tagger_using_fact_name(self):
        """Tests TorchTagger training with binary facts."""
        payload = {
            "description": "TestBinaryMulticlassTorchTaggerTraining",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3,
            "embedding": self.test_embedding_id,
            "pos_label": TEST_POS_LABEL,
            "query": json.dumps(TEST_BIN_FACT_QUERY)
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_binary_multiclass_torchtagger_training_and_task_signal:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check if f1 not NULL (train and validation success)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_torchtagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))

        print_output('test_torchtagger_has_classes:response.data.classes', response.data["classes"])
        self.assertTrue(isinstance(response.data["classes"], list))
        self.assertTrue(len(response.data["classes"]) == 2)
        # add cleanup
        self.add_cleanup_files(tagger_id)


    def run_train_binary_multiclass_tagger_using_fact_name_invalid_payload(self):
        """Tests TorchTagger training with binary facts and invalid payload."""

        # Pos label is undefined by the user
        invalid_payload_1 = {
            "description": "TestBinaryMulticlassTorchTaggerTrainingMissingPosLabel",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3,
            "embedding": self.test_embedding_id,
            "query": json.dumps(TEST_BIN_FACT_QUERY)
        }
        response = self.client.post(self.url, invalid_payload_1, format='json')
        print_output('test_create_binary_multiclass_torchtagger_using_fact_name_missing_pos_label:response.data', response.data)
        # Check if creating the Tagger fails with status code 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # The inserted pos label is not present in the data
        invalid_payload_2 = {
            "description": "TestBinaryMulticlassTorchTaggerTrainingMissingPosLabel",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3,
            "embedding": self.test_embedding_id,
            "query": json.dumps(TEST_BIN_FACT_QUERY),
            "pos_label": "invalid_fact_val"
        }
        response = self.client.post(self.url, invalid_payload_2, format='json')
        print_output('test_create_binary_multiclass_torchtagger_using_fact_name_invalid_pos_label:response.data', response.data)
        # Check if creating the Tagger fails with status code 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_train_balanced_multiclass_tagger_using_fact_name(self):
        """Tests TorchTagger training with multiple balanced classes and if a new Task gets created via the signal"""
        payload = {
            "description": "TestBalancedTorchTaggerTraining",
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 150,
            "model_architecture": self.torch_models[0],
            "num_epochs": 2,
            "embedding": self.test_embedding_id,
            "balance": True,
            "use_sentence_shuffle": True,
            "balance_to_max_limit": True
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_balanced_multiclass_torchtagger_training_and_task_signal:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check if f1 not NULL (train and validation success)
        tagger_id = response.data['id']
        response = self.client.get(f'{self.url}{tagger_id}/')
        print_output('test_balanced_torchtagger_has_stats:response.data', response.data)
        for score in ['f1_score', 'precision', 'recall', 'accuracy']:
            self.assertTrue(isinstance(response.data[score], float))

        num_examples = json.loads(response.data["num_examples"])
        print_output('test_balanced_torchtagger_num_examples_correct:num_examples', num_examples)
        for class_size in num_examples.values():
            self.assertTrue(class_size, payload["maximum_sample_size"])

        print_output('test_balanced_torchtagger_has_classes:classes', response.data["classes"])
        self.assertTrue(isinstance(response.data["classes"], list))
        self.assertTrue(len(response.data["classes"]) >= 2)
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
            "indices": [{"name": self.test_index_name}]
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
        self.assertTrue(len(response.data[0]) > 0)


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
            "indices": [{"name": self.test_index_name}]
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
        task_object = self.reindexer_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_binary_torch_tagger_to_index: waiting for reindexer task to finish, current status:', task_object.status)
            sleep(2)

        url = f'{self.url}{self.test_tagger_id}/apply_to_index/'

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
        tagger_object = TorchTagger.objects.get(pk=self.test_tagger_id)

        # Wait til the task has finished
        task_object = tagger_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_binary_torch_tagger_to_index: waiting for applying tagger task to finish, current status:', task_object.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_binary_torch_tagger_to_index:elastic aggerator results:", results)

        # Check if expected number of facts is added
        self.assertTrue(results[self.new_fact_value] > 10)


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

        tagger_orm: TorchTagger = TorchTagger.objects.get(pk=self.test_tagger_id)
        model_path = pathlib.Path(tagger_orm.model.path)
        print_output('run_tag_and_feedback_and_retrain:assert that previous model doesnt exist', data=model_path.exists())
        self.assertTrue(model_path.exists())

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

        # Ensure that previous tagger is deleted properly.
        print_output('test_model_retrain:assert that previous model doesnt exist', data=model_path.exists())
        self.assertFalse(model_path.exists())
        # Ensure that the freshly created model wasn't deleted.
        tagger_orm.refresh_from_db()
        self.assertNotEqual(tagger_orm.model.path, str(model_path))

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
