from time import time

from rest_framework.test import APITestCase
from rest_framework import status

from toolkit.test_settings import TEST_FIELD, TEST_INDEX_LARGE, TEST_FIELD_CHOICE, TEST_VERSION_PREFIX
from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file

class EmbeddingPerformanceTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')
        cls.user.is_superuser = True
        cls.user.save()
        cls.project = Project.objects.create(
            title='embeddingTestProject',
            indices=TEST_INDEX_LARGE
        )
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/embeddings/'

    def setUp(self):
        self.client.login(username='embeddingOwner', password='pw')

    def test_embedding_training_duration(self):
        print('Training Embedding')
        payload = {
            "description": "TestEmbedding",
            "query": "",
            "fields": TEST_FIELD_CHOICE,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        start_time = time()
        response = self.client.post(self.url, payload, format='json')
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        duration = time()-start_time
        print_output('test_embedding_training_duration:duration', duration)
