from io import BytesIO
import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE, TEST_QUERY, TEST_MATCH_TEXT
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
            indices=TEST_INDEX
        )
        cls.url = f'/projects/{cls.project.id}/taggers/'
        cls.project_url = f'/projects/{cls.project.id}'
        cls.multitag_text_url = f'/projects/{cls.project.id}/multitag_text/'

        # set vectorizer & classifier options
        cls.vectorizer_opts = ('Count Vectorizer',)# 'Hashing Vectorizer', 'TfIdf Vectorizer')
        cls.classifier_opts = ('Logistic Regression',)# 'LinearSVC')

        # list tagger_ids for testing. is populatated duriong training test
        cls.test_tagger_ids = []


    def setUp(self):
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_tagger_training_and_task_signal()
        #self.run_create_tagger_with_incorrect_fields()
        #self.run_tag_text(self.test_tagger_ids)
        #self.run_tag_text_with_lemmatization()
        #self.run_tag_doc()
        #self.run_tag_doc_with_lemmatization()
        #self.run_tag_random_doc()
        #self.run_stop_word_list()
        #self.run_stop_word_add()
        #self.run_stop_word_remove()
        #self.run_list_features()
        #self.run_multitag_text()
        #self.run_model_retrain()
        #self.run_model_export_import()
        self.run_tag_and_feedback()


    def run_create_tagger_training_and_task_signal(self):
        '''Tests the endpoint for a new Tagger, and if a new Task gets created via the signal'''
        # run test for each vectorizer & classifier option
        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                payload = {
                    "description": "TestTagger",
                    "query": json.dumps(TEST_QUERY),
                    "fields": TEST_FIELD_CHOICE,
                    "vectorizer": vectorizer_opt,
                    "classifier": classifier_opt,
                    "maximum_sample_size": 500,
                    "negative_multiplier": 1.0,
                }

                response = self.client.post(self.url, payload, format='json')
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


    def run_create_tagger_with_incorrect_fields(self):
        '''Tests the endpoint for a new Tagger with incorrect field data (should give error)'''
        payload = {
            "description": "TestTagger",
            "query": json.dumps(TEST_QUERY),
            "fields": ["randomgibberishhhhhhhhhh"],
            "vectorizer": self.vectorizer_opts[0],
            "classifier": self.classifier_opts[0],
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
        }        

        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_tagger_with_invalid_fields:response.data', response.data)
        # Check if Tagger gets rejected
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue('error' in response.data)


    def run_tag_text(self, test_tagger_ids):
        '''Tests the endpoint for the tag_text action'''
        payload = { "text": "This is some test text for the Tagger Test" }
        for test_tagger_id in test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_tag_text:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('result' in response.data)
            self.assertTrue('probability' in response.data)


    def run_tag_text_with_lemmatization(self):
        '''Tests the endpoint for the tag_text action'''
        payload = { "text": "See tekst peaks saama lemmatiseeritud ja täägitud.",
                    "lemmatize": True }
        for test_tagger_id in self.test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_tag_text_lemmatized:response.data', response.data)
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


    def run_tag_doc_with_lemmatization(self):
        '''Tests the endpoint for the tag_doc action'''
        payload = { "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test" }),
                    "lemmatize": True }
        for test_tagger_id in self.test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_doc/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_tag_doc_lemmatized:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('result' in response.data)
            self.assertTrue('probability' in response.data)


    def run_tag_random_doc(self):
        '''Tests the endpoint for the tag_random_doc action'''
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.url}{test_tagger_id}/tag_random_doc/'
            response = self.client.get(url)
            print_output('test_tag_random_doc:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response is list
            self.assertTrue(isinstance(response.data, dict))
            self.assertTrue('prediction' in response.data)


    def run_list_features(self):
        '''Tests the endpoint for the list_features action'''
        for test_tagger_id in self.test_tagger_ids:
            test_tagger_object = Tagger.objects.get(pk=test_tagger_id)
            # pass if using HashingVectorizer as it does not support feature listing
            if test_tagger_object.vectorizer != 'Hashing Vectorizer':
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
            url = f'{self.url}{test_tagger_id}/stop_word_add/'
            payload = {"text": "stopsõna"}
            response = self.client.post(url, payload, format='json')
            print_output('test_stop_word_add:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('added' in response.data)


    def run_stop_word_remove(self):
        for test_tagger_id in self.test_tagger_ids:
            '''Tests the endpoint for the stop_word_remove action'''
            url = f'{self.url}{test_tagger_id}/stop_word_remove/?text=stopsõna'
            payload = {"text": "stopsõna"}            
            response = self.client.post(url, payload, format='json')
            print_output('test_stop_word_remove:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('removed' in response.data)


    def run_multitag_text(self):
        '''Tests tagging with multiple models using multitag endpoint.'''
        payload = {"text": "Some sad text for tagging", "taggers": self.test_tagger_ids}
        response = self.client.post(self.multitag_text_url, payload, format='json')
        print_output('test_multitag:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def run_model_retrain(self):
        '''Tests the endpoint for the model_retrain action'''
        test_tagger_id = self.test_tagger_ids[0]
        # Check if stop word present in features
        url = f'{self.url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT in feature_dict)
        # add stop word before retraining
        url = f'{self.url}{test_tagger_id}/stop_word_add/'
        payload = {"text": TEST_MATCH_TEXT}
        response = self.client.post(url, payload, format='json')
        # retrain tagger
        url = f'{self.url}{test_tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        print_output('test_model_retrain:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # Check if stop word NOT present in features
        url = f'{self.url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT not in feature_dict)


    def run_model_export_import(self):
        '''Tests endpoint for model export and import'''
        test_tagger_id = self.test_tagger_ids[0]
        # retrieve model zip
        url = f'{self.url}{test_tagger_id}/export_model/'
        response = self.client.get(url)
        # post model zip
        import_url = f'{self.project_url}/import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Test tagging with imported model
        tagger_id = response.data['id']
        self.run_tag_text([tagger_id])


    def run_tag_and_feedback(self):
        '''Tests feeback extra action.'''
        tagger_id = self.test_tagger_ids[0]
        payload = {
            "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test" }),
            "feedback_enabled": True}
        tag_text_url = f'{self.url}{tagger_id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_doc_with_feedback:response.data', response.data)
        self.assertTrue('feedback' in response.data)
        # generate feedback
        fb_id = response.data['feedback']['id']
        feedback_url = f'{self.url}{tagger_id}/feedback/'
        payload = {"feedback_id": fb_id, "correct_prediction": True}
        response = self.client.post(feedback_url, payload, format='json')
        print_output('test_tag_doc_with_feedback:response.data', response.data)
        
        #    self.assertEqual(response.status_code, status.HTTP_200_OK)
        #    # Check if response data is not empty, but a result instead
        #    self.assertTrue(response.data)
        #    self.assertTrue('result' in response.data)
        #    self.assertTrue('probability' in response.data)