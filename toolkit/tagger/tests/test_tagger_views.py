import json
import os
import pathlib
from io import BytesIO
from time import sleep
from typing import List

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.core.task.models import Task
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (TEST_FIELD,
                                   TEST_FIELD_CHOICE,
                                   TEST_INDEX,
                                   TEST_MATCH_TEXT,
                                   TEST_QUERY,
                                   TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerViewTests(APITransactionTestCase):


    def setUp(self):
        # Owner of the project
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.multitag_text_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/multitag_text/'

        # set vectorizer & classifier options
        self.vectorizer_opts = ('Count Vectorizer', 'Hashing Vectorizer', 'TfIdf Vectorizer')
        self.classifier_opts = ('Logistic Regression', 'LinearSVC')

        # list tagger_ids for testing. is populated during training test
        self.test_tagger_ids = []
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_tagger_training_and_task_signal()
        self.run_create_tagger_with_incorrect_fields()
        self.run_tag_text(self.test_tagger_ids)
        self.run_tag_text_with_lemmatization()
        self.run_tag_doc()
        self.run_tag_doc_with_lemmatization()
        self.run_tag_random_doc()
        self.run_stop_word_list()
        self.run_stop_word_add()
        self.run_stop_word_replace()
        self.run_list_features()
        self.run_multitag_text()
        self.run_model_retrain()
        self.run_model_export_import()
        self.run_tag_and_feedback_and_retrain()
        self.create_tagger_with_empty_fields()
        self.create_tagger_then_delete_tagger_and_created_model()


    def tearDown(self) -> None:
        Tagger.objects.all().delete()


    def run_create_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger, and if a new Task gets created via the signal"""
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
                    "score_threshold": 0.1
                }

                response = self.client.post(self.url, payload, format='json')
                print_output('test_create_tagger_training_and_task_signal:response.data', response.data)
                # Check if Tagger gets created
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                created_tagger = Tagger.objects.get(id=response.data['id'])
                # add tagger to be tested
                self.test_tagger_ids.append(created_tagger.pk)
                # Check if not errors
                self.assertEqual(created_tagger.task.errors, '[]')
                # Remove tagger files after test is done
                self.addCleanup(remove_file, created_tagger.model.path)
                self.addCleanup(remove_file, created_tagger.plot.path)
                # Check if Task gets created via a signal
                self.assertTrue(created_tagger.task is not None)
                # Check if Tagger gets trained and completed
                self.assertEqual(created_tagger.task.status, Task.STATUS_COMPLETED)


    def run_create_tagger_with_incorrect_fields(self):
        """Tests the endpoint for a new Tagger with incorrect field data (should give error)"""
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
        self.assertTrue(response.exception)


    def create_tagger_then_delete_tagger_and_created_model(self):
        """ creates a tagger and removes it with DELETE in instance view """
        payload = {
            "description": "TestTagger",
            "query": json.dumps(TEST_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "vectorizer": "Hashing Vectorizer",
            "classifier": "Logistic Regression",
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0
        }

        create_response = self.client.post(self.url, payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        created_tagger_id = create_response.data['id']
        created_tagger_url = f'{self.url}{created_tagger_id}/'
        created_tagger_obj = Tagger.objects.get(id=created_tagger_id)
        model_location = created_tagger_obj.model.path
        plot_location = created_tagger_obj.plot.path

        delete_response = self.client.delete(created_tagger_url, format='json')
        print_output('delete_response.data: ', delete_response.data)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(os.path.isfile(model_location), False)
        self.assertEqual(os.path.isfile(plot_location), False)


    def create_tagger_with_empty_fields(self):
        """ tests to_repr serializer constant. Should fail because empty fields obj is filtered out in view"""
        payload = {
            "description": "TestTagger",
            "query": json.dumps(TEST_QUERY),
            "fields": [],
            "vectorizer": "Hashing Vectorizer",
            "classifier": "Logistic Regression",
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0
        }
        create_response = self.client.post(self.url, payload, format='json')
        print_output("empty_fields_response", create_response.data)
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_put_on_tagger_instances(self, test_tagger_ids):
        """ Tests put response success for Tagger fields """
        payload = {
            "description": "PutTagger",
            "query": json.dumps(TEST_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "vectorizer": 'Hashing Vectorizer',
            "classifier": 'Logistic Regression',
            "maximum_sample_size": 1000,
            "negative_multiplier": 3.0,
        }
        for test_tagger_id in test_tagger_ids:
            tagger_url = f'{self.url}{test_tagger_id}/'
            put_response = self.client.put(tagger_url, payload, format='json')
            print_output("put_response", put_response.data)
            self.assertEqual(put_response.status_code, status.HTTP_200_OK)


    def run_tag_text(self, test_tagger_ids: List[int]):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "This is some test text for the Tagger Test"}
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
        """Tests the endpoint for the tag_text action"""
        payload = {
            "text": "See tekst peaks saama lemmatiseeritud ja täägitud.",
            "lemmatize": True
        }
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
        """Tests the endpoint for the tag_doc action"""
        payload = {"doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"})}
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
        """Tests the endpoint for the tag_doc action"""
        payload = {
            "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"}),
            "lemmatize": True
        }
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
        """Tests the endpoint for the tag_random_doc action"""
        for test_tagger_id in self.test_tagger_ids:
            payload = {
                "indices": [{"name": TEST_INDEX}]
            }
            url = f'{self.url}{test_tagger_id}/tag_random_doc/'
            response = self.client.post(url, format="json", data=payload)
            print_output('test_tag_random_doc:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response is list
            self.assertTrue(isinstance(response.data, dict))
            self.assertTrue('prediction' in response.data)


    def run_list_features(self):
        """Tests the endpoint for the list_features action"""
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
        """Tests the endpoint for the stop_word_list action"""
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.url}{test_tagger_id}/stop_words/'
            response = self.client.get(url)
            print_output('run_stop_word_list:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)


    def run_stop_word_add(self):
        """Tests the endpoint for the stop_word_add action"""
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.url}{test_tagger_id}/stop_words/'
            payload = {"text": "stopsõna"}
            response = self.client.post(url, payload, format='json')
            print_output('run_stop_word_add:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)
            self.assertTrue('stopsõna' in response.data['stop_words'])


    def run_stop_word_replace(self):
        for test_tagger_id in self.test_tagger_ids:
            """Tests the endpoint for the stop_word_remove action"""
            # First add stop_words
            url = f'{self.url}{test_tagger_id}/stop_words/'
            payload = {"text": "stopsõna"}
            response = self.client.post(url, payload, format='json')

            # Then replace them
            payload = {"text": "sõnastop"}
            response = self.client.post(url, payload, format='json')
            print_output('run_stop_word_replace:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)
            self.assertTrue('stopsõna' not in response.data['stop_words'])
            self.assertTrue('sõnastop' in response.data['stop_words'])


    def run_multitag_text(self):
        """Tests tagging with multiple models using multitag endpoint."""
        payload = {"text": "Some sad text for tagging", "taggers": self.test_tagger_ids}
        response = self.client.post(self.multitag_text_url, payload, format='json')
        print_output('test_multitag:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def run_model_retrain(self):
        """Tests the endpoint for the model_retrain action"""
        test_tagger_id = self.test_tagger_ids[0]
        # Check if stop word present in features
        url = f'{self.url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT in feature_dict)
        # add stop word before retraining
        url = f'{self.url}{test_tagger_id}/stop_words/'
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
        """Tests endpoint for model export and import"""
        test_tagger_id = self.test_tagger_ids[0]

        # retrieve model zip
        url = f'{self.url}{test_tagger_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Test prediction with imported tagger
        imported_tagger_id = response.data['id']
        print_output('test_import_model:response.data', response.data)

        tagger = Tagger.objects.get(id=imported_tagger_id)

        tagger_model_dir = pathlib.Path(RELATIVE_MODELS_PATH) / "tagger"
        tagger_model_path = pathlib.Path(tagger.model.name)

        self.assertTrue(tagger_model_path.exists())

        # Check whether the model was saved into the right location.
        self.assertTrue(str(tagger_model_dir) in str(tagger.model.path))

        self.run_tag_text([imported_tagger_id])


    def run_tag_and_feedback_and_retrain(self):
        """Tests feeback extra action."""
        tagger_id = self.test_tagger_ids[0]
        payload = {
            "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"}),
            "feedback_enabled": True
        }
        tag_text_url = f'{self.url}{tagger_id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_doc_with_feedback:response.data', response.data)
        self.assertTrue('feedback' in response.data)

        # generate feedback
        fb_id = response.data['feedback']['id']
        feedback_url = f'{self.url}{tagger_id}/feedback/'
        payload = {"feedback_id": fb_id, "correct_result": "True"}
        response = self.client.post(feedback_url, payload, format='json')
        print_output('test_tag_doc_with_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)

        # list feedback
        feedback_list_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_doc_list_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue(len(response.data) > 0)

        # retrain model
        url = f'{self.url}{tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        # test tagging again for this model
        payload = {
            "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"})
        }
        tag_text_url = f'{self.url}{tagger_id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_feedback_retrained_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)

        # delete feedback
        feedback_delete_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.delete(feedback_delete_url)
        print_output('test_tag_doc_delete_feedback:response.data', response.data)
        # sleep for a sec to allow elastic to finish its business
        sleep(1)

        # list feedback again to make sure its emtpy
        feedback_list_url = f'{self.url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_doc_list_feedback_after_delete:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data) == 0)

        # remove created index
        feedback_index_url = f'{self.project_url}/feedback/'
        response = self.client.delete(feedback_index_url)
        print_output('test_delete_feedback_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('success' in response.data)
