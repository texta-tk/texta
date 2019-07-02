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
        # activate project
        cls.user.profile.activate_project(cls.project)

        # set vectorizer & classifier options
        cls.vectorizer_opts = (0, 2)
        cls.classifier_opts = (0, 1)
        cls.feature_selector_opts = (0, 1)

        # list tagger_ids for testing. is populatated duriong training test
        cls.test_tagger_ids = []


    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_tagger_training_and_task_signal()
        self.run_tag_text()
        self.run_tag_doc()
        self.run_stop_word_list()
        self.run_stop_word_add()
        self.run_stop_word_remove()
        self.run_list_features()


    def run_create_tagger_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger, and if a new Task gets created via the signal'''
        # run test for each vectorizer & classifier option
        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                for feature_selector_opt in self.feature_selector_opts:
                    payload = {
                        "description": "TestTagger",
                        "query": "",
                        "fields": TEST_FIELD_CHOICE,
                        "vectorizer": vectorizer_opt,
                        "classifier": classifier_opt,
                        "feature_selector": feature_selector_opt,
                        "maximum_sample_size": 500,
                        "negative_multiplier": 1.0,
                    }
                    response = self.client.post(self.url, payload)
                    print_output('test_create_tagger_training_and_task_signal:response.data', response.data)
                    # Check if Tagger gets created
                    self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                    created_tagger = Tagger.objects.get(id=response.data['id'])
                    # add tagger to be tested
                    self.test_tagger_ids.append(created_tagger.pk)
                    # Check if not errors
                    self.assertEqual(created_tagger.task.errors, '')
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
        print(self.test_tagger_ids)
        for test_tagger_id in self.test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
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
        for test_tagger_id in self.test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_doc/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_tag_doc:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('result' in response.data)
            self.assertTrue('probability' in response.data)


    def run_list_features(self):
        '''Tests the endpoint for the list_features action'''
        for test_tagger_id in self.test_tagger_ids:
            test_tagger_object = Tagger.objects.get(pk=test_tagger_id)
            # pass if using HashingVectorizer as it does not support feature listing
            if test_tagger_object.vectorizer != 0:
                list_features_url = f'{self.url}{test_tagger_id}/list_features/?size=10'
                response = self.client.get(list_features_url)
                print_output('test_list_features:response.data', response.data)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                # Check if response data is not empty, but a result instead
                self.assertTrue(response.data)
                self.assertTrue('features' in response.data)
    

    def run_stop_word_list(self):
        '''Tests the endpoint for the stop_word_list action'''
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.url}{test_tagger_id}/stop_word_list/'
            response = self.client.get(url)
            print_output('test_stop_word_list:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)  


    def run_stop_word_add(self):
        '''Tests the endpoint for the stop_word_add action'''
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.url}{test_tagger_id}/stop_word_add/?text=stopsõna'
            response = self.client.get(url)
            print_output('test_stop_word_add:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('added' in response.data)


    def run_stop_word_remove(self):
        for test_tagger_id in self.test_tagger_ids:
            '''Tests the endpoint for the stop_word_remove action'''
            url = f'{self.url}{test_tagger_id}/stop_word_remove/?text=stopsõna'
            response = self.client.get(url)
            print_output('test_stop_word_remove:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('removed' in response.data)
