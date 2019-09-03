import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_FACT_NAME
from toolkit.core.project.models import Project
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file


class TaggerGroupViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='taggerGroupTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        cls.url = f'/projects/{cls.project.id}/tagger_groups/'
        cls.test_tagger_group_id = None


    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_tagger_group_training_and_task_signal()
        self.run_tag_text()
        self.run_tag_doc()
        self.run_tag_random_doc()
        self.run_models_retrain()


    def run_create_tagger_group_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger Group, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_tagger_group_training_and_task_signal:response.data', response.data)
        # Check if TaggerGroup gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # add tagger to be tested
        created_tagger_group = TaggerGroup.objects.get(id=response.data['id'])
        self.test_tagger_group_id = created_tagger_group.pk

        for tagger in created_tagger_group.taggers.all():
            # run this for each tagger in tagger group
            # Remove tagger files after test is done
            self.addCleanup(remove_file, json.loads(tagger.location)['tagger'])
            self.addCleanup(remove_file, tagger.plot.path)
            # Check if not errors
            self.assertEqual(tagger.task.errors, '')
            # Check if Task gets created via a signal
            self.assertTrue(tagger.task is not None)
            # Check if Tagger gets trained and completed
            self.assertEqual(tagger.task.status, Task.STATUS_COMPLETED)


    def run_tag_text(self):
        '''Tests the endpoint for the tag_text action'''
        payload = { "text": "see on mingi suvaline naisteka kommentaar. ehk joppab ja saab täägi",
                    "show_candidates": True }
        tag_text_url = f'{self.url}{self.test_tagger_group_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_text_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('decision' in response.data[0])


    def run_tag_doc(self):
        '''Tests the endpoint for the tag_doc action'''
        payload = { "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test" }), 
                    "show_candidates": True }
        url = f'{self.url}{self.test_tagger_group_id}/tag_doc/'
        response = self.client.post(url, payload)
        print_output('test_tag_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue('decision' in response.data[0])


    def run_tag_random_doc(self):
        '''Tests the endpoint for the tag_random_doc action'''
        url = f'{self.url}{self.test_tagger_group_id}/tag_random_doc/'
        response = self.client.get(url)
        print_output('test_tag_random_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('tags' in response.data)


    def run_models_retrain(self):
        '''Tests the endpoint for the models_retrain action'''
        url = f'{self.url}{self.test_tagger_group_id}/models_retrain/'
        response = self.client.post(url)
        print_output('test_models_retrain:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)