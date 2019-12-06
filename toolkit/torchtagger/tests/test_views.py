from io import BytesIO
from time import sleep
import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_FACT_NAME
from toolkit.core.project.models import Project
from toolkit.torchtagger.models import TorchTagger
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.torchtagger.torch_models.models import TORCH_MODELS


class TorchTaggerViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('torchTaggerOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='torchTaggerTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        cls.url = f'/projects/{cls.project.id}/torchtaggers/'
        cls.project_url = f'/projects/{cls.project.id}'
        cls.test_embedding_id = None
        cls.torch_models = list(TORCH_MODELS.keys())
        cls.test_tagger_id = None

    def setUp(self):
        self.client.login(username='torchTaggerOwner', password='pw')

    def test(self):
        self.run_train_embedding()
        self.run_train_tagger()
        self.run_train_multiclass_tagger()
        self.run_tag_text()
        self.run_tag_random_doc()
        self.run_tag_and_feedback_and_retrain()

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
        embeddings_url = f'/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, payload, format='json')
        self.test_embedding_id = response.data["id"]

    def run_train_tagger(self):
        '''Tests TorchTagger training, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestTorchTaggerTraining",
            #"fact_name": TEST_FACT_NAME,
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
        # Remove tagger files after test is done
        self.addCleanup(remove_file, response.data['location']['torchtagger'])
        #self.addCleanup(remove_file, created_tagger.plot.path)

    def run_train_multiclass_tagger(self):
        '''Tests TorchTagger training with multiple classes and if a new Task gets created via the signal'''
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
        # Remove tagger files after test is done
        self.addCleanup(remove_file, response.data['location']['torchtagger'])
        #self.addCleanup(remove_file, created_tagger.plot.path)

    def run_tag_text(self):
        '''Tests tag prediction for texts.'''
        payload = {
            "text": "mine kukele, kala"
        }
        response = self.client.post(f'{self.url}{self.test_tagger_id}/tag_text/', payload)
        print_output('test_torchtagger_tag_text:response.data', response.data)

    def run_tag_random_doc(self):
        '''Tests the endpoint for the tag_random_doc action'''
        url = f'{self.url}{self.test_tagger_id}/tag_random_doc/'
        response = self.client.get(url)
        print_output('test_tag_random_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('prediction' in response.data)

    def run_model_retrain(self):
        '''Tests the endpoint for the model_retrain action'''
        test_tagger_id = self.test_tagger_ids[0]
        # Check if stop word present in features
        url = f'{self.url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT in feature_dict)
        # add stop word before retraining
        url = f'{self.url}{test_tagger_id}/stop_words/'
        payload = {"text": TEST_MATCH_TEXT}
        response = self.client.post(url, payload, format='json')
        # retrain tagger
        url = f'{self.url}{test_tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        print_output('test_model_retrain:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # Check if stop word NOT present in features
        url = f'{self.url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT not in feature_dict)


    def run_model_export_import(self):
        '''Tests endpoint for model export and import'''
        test_tagger_id = self.test_tagger_ids[0]
        # retrieve model zip
        url = f'{self.url}{test_tagger_id}/export_model/'
        response = self.client.get(url)
        # post model zip
        import_url = f'{self.project_url}/import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Test tagging with imported model
        tagger_id = response.data['id']
        self.run_tag_text([tagger_id])


    def run_tag_and_feedback_and_retrain(self):
        '''Tests feeback extra action.'''
        tagger_id = self.test_tagger_id
        payload = {
            "text": "This is some test text for the Tagger Test",
            "feedback_enabled": True}
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
