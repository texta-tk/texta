from io import BytesIO
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

    def setUp(self):
        self.client.login(username='torchTaggerOwner', password='pw')

    def test(self):
        self.run_train_embedding()
        self.run_train_tagger()

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
            "fact_name": TEST_FACT_NAME,
            "fields": TEST_FIELD_CHOICE,
            "maximum_sample_size": 500,
            #"model_architecture": "fastText",
            "embedding": 1,
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_torchtagger_training_and_task_signal:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
