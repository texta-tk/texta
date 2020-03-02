import pathlib
from io import BytesIO
from time import sleep

from django.test import TransactionTestCase
from rest_framework import status

from toolkit.core.project.models import Project
from toolkit.test_settings import (TEST_FACT_NAME, TEST_FIELD_CHOICE, TEST_INDEX, TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.torchtagger.models import TorchTagger
from toolkit.torchtagger.torch_models.models import TORCH_MODELS


class TorchTaggerViewTests(TransactionTestCase):
    def setUp(self):
        # Owner of the project
        self.user = create_test_user('torchTaggerOwner', 'my@email.com', 'pw')
        self.project = Project.objects.create(
            title='torchTaggerTestProject',
            indices=TEST_INDEX
        )
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/torchtaggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.test_embedding_id = None
        self.torch_models = list(TORCH_MODELS.keys())
        self.test_tagger_id = None

        self.client.login(username='torchTaggerOwner', password='pw')


    def test(self):
        self.run_train_embedding()
        self.run_train_tagger()
        self.run_train_multiclass_tagger()
        self.run_tag_text()
        self.run_tag_random_doc()
        self.run_tag_and_feedback_and_retrain()
        self.run_model_export_import()


    def add_cleanup_files(self, tagger_id):
        tagger_object = TorchTagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        self.addCleanup(remove_file, tagger_object.text_field.path)
        self.addCleanup(remove_file, tagger_object.plot.path)
        self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)
        self.addCleanup(remove_file, tagger_object.embedding.phraser_model.path)


    def run_train_embedding(self):
        # payload for training embedding
        payload = {
            "description": "TestEmbedding",
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 300,
        }
        # post
        embeddings_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, payload, format='json')
        self.test_embedding_id = response.data["id"]


    def run_train_tagger(self):
        """Tests TorchTagger training, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestTorchTaggerTraining",
            # "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            "model_architecture": self.torch_models[0],
            "num_epochs": 3,
            "embedding": self.test_embedding_id,
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_torchtagger_training_and_task_signal:response.data', response.data)
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


    def run_train_multiclass_tagger(self):
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
        print_output('test_create_torchtagger_training_and_task_signal:response.data', response.data)
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


    def run_tag_text(self):
        """Tests tag prediction for texts."""
        payload = {
            "text": "mine kukele, kala"
        }
        response = self.client.post(f'{self.url}{self.test_tagger_id}/tag_text/', payload)
        print_output('test_torchtagger_tag_text:response.data', response.data)


    def run_tag_random_doc(self):
        """Tests the endpoint for the tag_random_doc action"""
        url = f'{self.url}{self.test_tagger_id}/tag_random_doc/'
        response = self.client.get(url)
        print_output('test_tag_random_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('prediction' in response.data)


    def run_model_export_import(self):
        """Tests endpoint for model export and import"""
        test_tagger_group_id = self.test_tagger_id

        # retrieve model zip
        url = f'{self.url}{test_tagger_group_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
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
        response = self.client.get(url)
        print_output('test_tag_random_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))

        self.assertTrue('prediction' in response.data)


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
        payload = {"feedback_id": fb_id, "correct_prediction": "FUBAR"}
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
