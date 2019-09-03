import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file

class EmbeddingViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')

        cls.project = Project.objects.create(
            title='embeddingTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )

        cls.url = f'/projects/{cls.project.id}/embeddings/'
        cls.cluster_url = f'/projects/{cls.project.id}/embedding_clusters/'
        
        #cls.user.profile.activate_project(cls.project)

        cls.test_embedding_id = None
        cls.test_embedding_clustering_id = None


    def setUp(self):
        self.client.login(username='embeddingOwner', password='pw')


    def test_run(self):
        self.run_create_embedding_training_and_task_signal()
        self.run_predict()
        self.run_predict_with_negatives()
        self.run_phrase()
        self.run_create_embedding_cluster_training_and_task_signal()
        self.run_embedding_cluster_browse()
        self.run_embedding_cluster_find_word()
        self.run_embedding_cluster_text()


    def run_create_embedding_training_and_task_signal(self):
        '''Tests the endpoint for a new Embedding, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestEmbedding",
            "query": "",
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }

        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_embedding_training_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_embedding_id = created_embedding.id
        # Remove Embedding files after test is done
        print(created_embedding.task.status)
        self.addCleanup(remove_file, json.loads(created_embedding.location)['embedding'])
        self.addCleanup(remove_file, json.loads(created_embedding.location)['phraser'])
        # Check if Task gets created via a signal
        self.assertTrue(created_embedding.task is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(created_embedding.task.status, Task.STATUS_COMPLETED)


    def run_predict(self):
        '''Tests the endpoint for the predict action'''
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = { "positives": ["eesti", "läti"] }
        predict_url = f'{self.url}{self.test_embedding_id}/predict/'
        response = self.client.post(predict_url, payload)
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_predict_with_negatives(self):
        '''Tests the endpoint for the predict action'''
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = { "positives": ["eesti", "läti"], "negatives": ["juhtuma"] }
        predict_url = f'{self.url}{self.test_embedding_id}/predict/'
        response = self.client.post(predict_url, payload)
        print_output('predict_with_negatives:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_phrase(self):
        '''Tests the endpoint for the predict action'''
        payload = { "text": "See on mingi eesti keelne tekst testimiseks" }
        predict_url = f'{self.url}{self.test_embedding_id}/phrase/'
        response = self.client.post(predict_url, payload)
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)
    

    def run_create_embedding_cluster_training_and_task_signal(self):
        '''Tests the endpoint for a new EmbeddingCluster, and if a new Task gets created via the signal'''
        payload = {
            "embedding": self.test_embedding_id,
            "num_clusters": 10
        }

        response = self.client.post(self.cluster_url, payload)
        print_output('test_create_embedding_clustering_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding_cluster = EmbeddingCluster.objects.get(id=response.data['id'])
        self.test_embedding_clustering_id = created_embedding_cluster.id
        # Check if not errors
        self.assertEqual(created_embedding_cluster.task.errors, '')
        # Check if Task gets created via a signal
        self.assertTrue(created_embedding_cluster.task is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(created_embedding_cluster.task.status, Task.STATUS_COMPLETED)


    def run_embedding_cluster_browse(self):
        '''Tests the endpoint for the browse action'''
        payload = { "number_of_clusters": 10, "cluster_order": True }
        browse_url = f'{self.cluster_url}{self.test_embedding_clustering_id}/browse/'
        response = self.client.post(browse_url, payload)
        print_output('browse:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_embedding_cluster_find_word(self):
        '''Tests the endpoint for the find_word action'''
        payload = { "text": "putin" }
        browse_url = f'{self.cluster_url}{self.test_embedding_clustering_id}/find_word/'
        response = self.client.post(browse_url, payload)
        print_output('find_word:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_embedding_cluster_text(self):
        '''Tests the endpoint for the find_word action'''
        payload = { "text": "putin ja teised reptiloidid nagu ansip ja kallas. nats ja nats" }
        browse_url = f'{self.cluster_url}{self.test_embedding_clustering_id}/cluster_text/'
        response = self.client.post(browse_url, payload)
        print_output('cluster_text:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)
    