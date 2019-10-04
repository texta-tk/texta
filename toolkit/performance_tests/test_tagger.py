import json
import os
from time import time
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX_LARGE, TEST_FIELD_CHOICE, TEST_QUERY
from toolkit.core.project.models import Project
from toolkit.tagger.models import Tagger
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file

class TaggerViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='taggerTestProject',
            owner=cls.user,
            indices=TEST_INDEX_LARGE
        )
        cls.url = f'/projects/{cls.project.id}/taggers/'

    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')

    def test_tagger_training_duration(self):
        print('Training Tagger')
        payload = {
                    "description": "TestTagger",
                    "query": json.dumps(TEST_QUERY),
                    "fields": TEST_FIELD_CHOICE,
                    "vectorizer": "Hashing Vectorizer",
                    "classifier": "LinearSVC",
                    "maximum_sample_size": 3000,
                    "negative_multiplier": 1.0,
                }
        start_time = time()
        response = self.client.post(self.url, payload, format='json')
        # Check if Tagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duration = time()-start_time
        print_output('test_tagger_training_duration:duration', duration)