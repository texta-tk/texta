import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.core.project.models import Project
from toolkit.tagger.models import Tagger
from toolkit.core.task.models import Task
from toolkit.utils.utils_for_tests import create_test_user, print_output, remove_file

class TaggerViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.url = f'/taggers/'
        cls.user = create_test_user('taggerOwner', 'my@email.com', 'pw')

        cls.project = Project.objects.create(
            title='taggerTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )

        cls.user.profile.activate_project(cls.project)

        cls.test_tagger = Tagger.objects.create(
            description='TaggerForTesting',
            project=cls.project,
            author=cls.user,
            vectorizer=0,
            classifier=0,
            fields=TEST_FIELD_CHOICE,
            maximum_sample_size=500,
            negative_multiplier=1.0,
        )
        # Get the object, since .create does not update on changes
        cls.test_tagger = Tagger.objects.get(id=cls.test_tagger.id)


    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_tagger_training_and_task_signal()
        self.run_tag_text()
        self.run_tag_doc()


    def run_create_tagger_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestTagger",
            "query": "",
            "fields": TEST_FIELD_CHOICE,
            "vectorizer": 0,
            "classifier": 0,
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
        }

        response = self.client.post(self.url, payload)
        print_output('test_create_tagger_training_and_task_signal:response.data', response.data)
        # Check if Tagger gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_tagger = Tagger.objects.get(id=response.data['id'])
        # Remove tagger files after test is done
        self.addCleanup(remove_file, json.loads(created_tagger.location)['tagger'])
        self.addCleanup(remove_file, created_tagger.plot.path)
        # Check if Task gets created via a signal
        self.assertTrue(created_tagger.task is not None)
        # Check if Tagger gets trained and completed
        self.assertEqual(created_tagger.task.status, Task.STATUS_COMPLETED)


    def run_tag_text(self):
        '''Tests the endpoint for the tag_text action'''
        payload = { "text": "This is some test text for the Tagger Test" }
        tag_text_url = f'{self.url}{self.test_tagger.id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_text:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)


    def run_tag_doc(self):
        '''Tests the endpoint for the tag_doc action'''
        payload = { "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test" })}
        tag_text_url = f'{self.url}{self.test_tagger.id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)


    @classmethod
    def tearDownClass(cls):
        remove_file(json.loads(cls.test_tagger.location)['tagger'])
        remove_file(cls.test_tagger.plot.path)
