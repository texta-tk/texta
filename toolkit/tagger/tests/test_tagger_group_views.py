import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.core.project.models import Project
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.core.task.models import Task
from toolkit.utils.utils_for_tests import create_test_user, print_output, remove_file

class TaggerGroupViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.url = f'/tagger_groups/'
        cls.user = create_test_user('taggerOwner', 'my@email.com', 'pw')

        cls.project = Project.objects.create(
            title='taggerGroupTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )

        cls.user.profile.activate_project(cls.project)
        cls.test_tagger_group_ids = []


    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_tagger_group_training_and_task_signal()


    def run_create_tagger_group_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger Group, and if a new Task gets created via the signal'''

        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": "TEEMA",
            "tagger": {
                "query": "",
                "fields": [TEST_FIELD_CHOICE],
                "vectorizer": 0,
                "classifier": 0,
                "feature_selector": 0,
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_tagger_group_training_and_task_signal:response.data', response.data)
        # Check if TaggerGroup gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
