import json
import os
from time import time
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX_LARGE, TEST_FIELD_CHOICE, TEST_FACT_NAME
from toolkit.core.project.models import Project
from toolkit.neurotagger.models import Neurotagger
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.neurotagger import choices
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.neurotagger.tasks import neurotagger_train_handler


class NeurotaggerPerformanceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('neurotaggerOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='neurotaggerTestProject',
            owner=cls.user,
            indices=TEST_INDEX_LARGE
        )
        cls.url = f'/projects/{cls.project.id}/neurotaggers/'

    def setUp(self):
        self.client.login(username='neurotaggerOwner', password='pw')

    def test_neurotagger_training_duration(self):
        print('Training Neurotagger')
        payload = {
            "description": "TestNeurotaggerView",
            "fact_name": TEST_FACT_NAME,
            "model_architecture": choices.model_arch_choices[0][0],
            "fields": TEST_FIELD_CHOICE,
        }
        start_time = time()
        response = self.client.post(self.url, payload, format='json')
        print_output('test_neurotagger_training_duration:response.data', response.data)
        # Check if Neurotagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duration = time()-start_time
        print_output('test_neurotagger_training_duration:duration', duration)
