import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding
from toolkit.core.task.models import Task
from toolkit.utils.utils_for_tests import create_test_user, print_output, remove_file

class EmbeddingViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.url = f'/embeddings/'
        cls.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')

        cls.project = Project.objects.create(
            title='embeddingTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )

        cls.user.profile.activate_project(cls.project)

        cls.test_embedding = Embedding.objects.create(
            description='EmbeddingForTesting',
            project=cls.project,
            author=cls.user,
            fields=TEST_FIELD_CHOICE,
            min_freq=5,
            max_vocab=10000,
            num_dimensions=100,
        )
        # Get the object, since .create does not update on changes
        cls.test_embedding = Embedding.objects.get(id=cls.test_embedding.id)


    def setUp(self):
        self.client.login(username='embeddingOwner', password='pw')
    


    def test_create_embedding_training_and_task_signal(self):
        '''Tests the endpoint for a new Embedding, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestEmbedding",
            "query": "",
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }

        response = self.client.post(self.url, payload)
        print_output('test_create_embedding_training_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        # Remove Embedding files after test is done
        self.addCleanup(remove_file, json.loads(created_embedding.location)['embedding'])
        self.addCleanup(remove_file, json.loads(created_embedding.location)['phraser'])
        # Check if Task gets created via a signal
        self.assertTrue(created_embedding.task is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(created_embedding.task.status, Task.STATUS_COMPLETED)


    # def test_tag_text(self):
    #     '''Tests the endpoint for the tag_text action'''
    #     payload = { "text": "This is some test text for the Tagger Test" }
    #     tag_text_url = f'{self.url}{self.test_tagger.id}/tag_text/'
    #     response = self.client.post(tag_text_url, payload)
    #     print_output('test_tag_text:response.data', response.data)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     # Check if response data is not empty, but a result instead
    #     self.assertTrue(response.data)
    #     self.assertTrue('result' in response.data)
    #     self.assertTrue('probability' in response.data)


    # def test_tag_doc(self):
    #     '''Tests the endpoint for the tag_doc action'''
    #     payload = { "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test" })}
    #     tag_text_url = f'{self.url}{self.test_tagger.id}/tag_doc/'
    #     response = self.client.post(tag_text_url, payload)
    #     print_output('test_tag_doc:response.data', response.data)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     # Check if response data is not empty, but a result instead
    #     self.assertTrue(response.data)
    #     self.assertTrue('result' in response.data)
    #     self.assertTrue('probability' in response.data)


    @classmethod
    def tearDownClass(cls):
        remove_file(json.loads(cls.test_embedding.location)['embedding'])
        remove_file(json.loads(cls.test_embedding.location)['phraser'])
