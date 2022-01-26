import json
import os
from time import time
from django.db.models import signals

from django.test import TransactionTestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import (
    TEST_FIELD,
    TEST_INDEX_LARGE,
    TEST_FIELD_CHOICE,
    TEST_FACT_NAME,
    TEST_VERSION_PREFIX
)
from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import project_creation
from toolkit.torchtagger.models import TorchTagger
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from texta_elastic.searcher import EMPTY_QUERY
from toolkit.torchtagger.torch_models.models import TORCH_MODELS


class TorchTaggerPerformanceTests(TransactionTestCase):

    def setUp(self):
        self.user = create_test_user('torchtaggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("torchtaggerTestProject", TEST_INDEX_LARGE, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/torchtaggers/'
        self.test_embedding_id = None
        self.client.login(username='torchtaggerOwner', password='pw')
        self.torch_models = list(TORCH_MODELS.keys())


    def test(self):
        self.run_train_embedding_duration()
        self.run_torchtagger_training_duration()

    def run_train_embedding_duration(self):
        print('Training Embedding for TorchTagger...')
        # payload for training embedding
        payload = {
            "description": "TestEmbedding",
            "fields": TEST_FIELD_CHOICE,
            "min_freq": 5,
            "num_dimensions": 300,
        }
        start_time = time()
        # post
        embeddings_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        response = self.client.post(embeddings_url, payload, format='json')
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duration = time()-start_time
        print_output('test_embedding_training_duration:duration', duration)
        self.test_embedding_id = response.data["id"]


    def run_torchtagger_training_duration(self):
        print('Training TorchTagger...')
        payload = {
            "description": "TestTorchTaggerTraining",
            "fields": TEST_FIELD_CHOICE,
            "model_architecture": self.torch_models[0],
            "num_epochs": 5,
            "embedding": self.test_embedding_id,
        }
        start_time = time()
        response = self.client.post(self.url, payload, format='json')
        print_output('test_torchtagger_training_duration:response.data', response.data)
        # Check if TorchTagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duration = time()-start_time
        print_output('test_torchtagger_training_duration:duration', duration)

