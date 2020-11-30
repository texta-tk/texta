import json
from time import time

from django.test import override_settings
from rest_framework.test import APITestCase
from rest_framework import status

from toolkit.test_settings import(TEST_INDEX_LARGE,
                                  TEST_FIELD_CHOICE,
                                  TEST_QUERY,
                                  TEST_VERSION_PREFIX)
from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import project_creation
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerPerformanceTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        cls.user.is_superuser = True
        cls.user.save()
        cls.project = project_creation("taggerTestProject", TEST_INDEX_LARGE, cls.user)
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/taggers/'

    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')

    def test_tagger_training_duration(self):
        print('Training Tagger...')
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
