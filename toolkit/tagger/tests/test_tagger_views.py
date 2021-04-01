import json
import os
import pathlib
import uuid
from io import BytesIO
from time import sleep
from typing import List

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.core import ElasticCore
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (TEST_FIELD, TEST_FIELD_CHOICE, TEST_INDEX, TEST_KEEP_PLOT_FILES, TEST_MATCH_TEXT, TEST_QUERY, TEST_TAGGER_BINARY, TEST_VERSION_PREFIX, VERSION_NAMESPACE)
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
        self.multitag_text_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/multitag_text/'

        # set vectorizer & classifier options
        self.vectorizer_opts = ('Count Vectorizer', 'Hashing Vectorizer', 'TfIdf Vectorizer')
        self.classifier_opts = ('Logistic Regression', 'LinearSVC')

        # list tagger_ids for testing. is populated during training test
        self.test_tagger_ids = []
        self.client.login(username='taggerOwner', password='pw')

        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_TAGGER_NAME"
        self.new_fact_value = "TEST_TAGGER_VALUE"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying taggers",
            "indices": [TEST_INDEX],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])

        self.test_imported_binary_tagger_id = self.import_test_model(TEST_TAGGER_BINARY)


    def import_test_model(self, file_path: str):
        """Import models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.url}import_model/'
        resp = self.client.post(import_url, data={'file': open(file_path, "rb")}).json()
        print_output("Importing test model:", resp)
        return resp["id"]

    def __train_embedding_for_tagger(self) -> int:
        url = reverse(f"{VERSION_NAMESPACE}:embedding-list", kwargs={"project_pk": self.project.pk})
        payload = {
            "description": "TestEmbedding",
            "fields": [TEST_FIELD],
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("__train_embedding_for_tagger:response.data", response.data)
        return response.data["id"]


    def test_training_tagger_with_embedding(self):
        url = reverse(f"{VERSION_NAMESPACE}:tagger-list", kwargs={"project_pk": self.project.pk})
        embedding_id = self.__train_embedding_for_tagger()
        payload = {
            "description": "TestTagger",
            "query": json.dumps(TEST_QUERY),
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "classifier": "LinearSVC",
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "embedding": embedding_id
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_training_tagger_with_embedding:response.data", response.data)
        self.run_tag_text([response.data["id"]])
        self.add_cleanup_files(response.data["id"])


    def test_run(self):
        self.run_create_tagger_training_and_task_signal()
        self.run_create_tagger_with_incorrect_fields()
        self.run_tag_text(self.test_tagger_ids)
        self.run_tag_text_result_check([self.test_tagger_ids[-1]])
        self.run_tag_text_with_lemmatization()
        self.run_tag_doc()
        self.run_tag_doc_with_lemmatization()
        self.run_tag_random_doc()
        self.run_stop_word_list()
        self.run_stop_word_add_and_replace()
        self.run_list_features()
        self.run_multitag_text()
        self.run_model_retrain()
        self.run_model_export_import()
        self.run_apply_tagger_to_index()
        self.run_apply_tagger_to_index_invalid_input()
        self.run_tag_and_feedback_and_retrain()
        self.create_tagger_with_empty_fields()
        self.create_tagger_then_delete_tagger_and_created_model()


    def add_cleanup_files(self, tagger_id):
        tagger_object = Tagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)
        if tagger_object.embedding:
            self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)


    def tearDown(self) -> None:
        Tagger.objects.all().delete()
        res = ElasticCore().delete_index(self.test_index_copy)
        print_output(f"Delete apply_taggers test index {self.test_index_copy}", res)


    def run_create_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger, and if a new Task gets created via the signal"""
        lemmatize = True
        # run test for each vectorizer & classifier option
        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                payload = {
                    "description": "TestTagger",
                    "query": json.dumps(TEST_QUERY),
                    "fields": TEST_FIELD_CHOICE,
                    "indices": [{"name": TEST_INDEX}],
                    "lemmatize": lemmatize,
                    "vectorizer": vectorizer_opt,
                    "classifier": classifier_opt,
                    "maximum_sample_size": 500,
                    "negative_multiplier": 1.0,
                    "score_threshold": 0.1,
                    "stop_words": ["asdfghjkl"]
                }
                # as lemmatization is slow, do it only once
                lemmatize = False
                # procees to analyze result
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
                self.add_cleanup_files(created_tagger.id)
                # Check if Task gets created via a signal
                self.assertTrue(created_tagger.task is not None)
                # Check if Tagger gets trained and completed
                self.assertEqual(created_tagger.task.status, Task.STATUS_COMPLETED)


    def run_create_tagger_with_incorrect_fields(self):
        """Tests the endpoint for a new Tagger with incorrect field data (should give error)"""
        payload = {
            "description": "TestTagger",
            "query": json.dumps(TEST_QUERY),
            "indices": [{"name": TEST_INDEX}],
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
            "indices": [{"name": TEST_INDEX}],
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
            "indices": [{"name": TEST_INDEX}],
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
            "indices": [{"name": TEST_INDEX}],
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


    def run_tag_text_result_check(self, test_tagger_ids: List[int]):
        """Tests the endpoint to check if the tagger result corresponds to the input text."""
        payload_pos = {"text": "This is some test text for the Tagger Test loll"}
        payload_neg = {"text": "This is some test text for the Tagger Test"}

        payloads = {True: payload_pos, False: payload_neg}

        for label, payload in list(payloads.items()):
            for test_tagger_id in test_tagger_ids:
                tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
                response = self.client.post(tag_text_url, payload)
                print_output(f'test_tag_text_result_check_{label}:response.data', response.data)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data['result'], label)


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
                list_features_get_url = f'{self.url}{test_tagger_id}/list_features/?size=10'
                response = self.client.get(list_features_get_url)
                print_output('test_list_features:response.data', response.data)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                # Check if response data is not empty, but a result instead
                self.assertTrue(response.data)
                self.assertTrue('features' in response.data)
                self.assertTrue('total_features' in response.data)
                self.assertTrue('showing_features' in response.data)
                self.assertTrue(response.data['total_features'] >= response.data['showing_features'])
                # Check if any features listed
                self.assertTrue(len(response.data['features']) > 0)

                list_features_post_url = f'{self.url}{test_tagger_id}/list_features/'
                response = self.client.post(list_features_post_url, format="json", data={"size": 10})
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertTrue('features' in response.data)
                self.assertTrue('total_features' in response.data)
                self.assertTrue('showing_features' in response.data)
                self.assertTrue(response.data['total_features'] >= response.data['showing_features'])
                self.assertTrue(len(response.data['features']) > 0)


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


    def run_stop_word_add_and_replace(self):
        """Tests the endpoint for the stop_word_add action"""
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.url}{test_tagger_id}/stop_words/'
            payload = {'stop_words': ['stopsõna']}
            response = self.client.post(url, payload, format='json')
            print_output('run_stop_word_add_and_replace:add_new:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)
            self.assertTrue('stopsõna' in response.data['stop_words'])

            # Add new stop words to the existing one
            payload = {'stop_words': ['stopsõna2', 'stopsõna3'], 'overwrite_existing': False}
            response = self.client.post(url, payload, format='json')
            print_output('run_stop_word_add_and_replace:append_to_current_list:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if all the added stop words are present in response data
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)
            self.assertTrue('stopsõna' in response.data['stop_words'])
            self.assertTrue('stopsõna2' in response.data['stop_words'])
            self.assertTrue('stopsõna3' in response.data['stop_words'])

            # Add new stop words and overwrite the existing ones
            payload = {'stop_words': ['stopsõna4'], 'overwrite_existing': True}
            response = self.client.post(url, payload, format='json')
            print_output('run_stop_word_add_and_replace:overwrite_existing:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if all the added stop words are present in response data
            self.assertTrue(response.data)
            # Check if the old stop words are replaced
            self.assertTrue('stop_words' in response.data)
            self.assertTrue('stopsõna4' in response.data['stop_words'])
            self.assertFalse('stopsõna' in response.data['stop_words'])


    def run_multitag_text(self):
        """Tests tagging with multiple models using multitag endpoint."""
        payload = {"text": "Some sad text for tagging", "taggers": self.test_tagger_ids}
        response = self.client.post(self.multitag_text_url, payload, format='json')
        print_output('test_multitag:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def run_apply_tagger_to_index(self):
        """Tests applying tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        test_tagger_id = self.test_imported_binary_tagger_id
        url = f'{self.url}{test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "new_fact_value": self.new_fact_value,
            "indices": [{"name": self.test_index_copy}],
            "fields": [TEST_FIELD],
            "lemmatize": False
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = Tagger.objects.get(pk=test_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_tagger_to_index:elastic aggerator results:", results)

        # Check if expected number of facts are added to the index
        expected_number_of_facts = 30
        self.assertTrue(results[self.new_fact_value] == expected_number_of_facts)
        self.add_cleanup_files(test_tagger_id)


    def run_apply_tagger_to_index_invalid_input(self):
        """Tests applying tagger to index using apply_to_index endpoint with invalid input."""

        test_tagger_id = self.test_tagger_ids[0]
        url = f'{self.url}{test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "new_fact_value": self.new_fact_value,
            "fields": "invalid_field_format",
            "lemmatize": False,
            "bulk_size": 100
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_to_index_invalid_input:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


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
        payload = {"stop_words": [TEST_MATCH_TEXT], 'overwrite_existing': True}
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
        self.add_cleanup_files(test_tagger_id)


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
        self.add_cleanup_files(test_tagger_id)
        self.add_cleanup_files(imported_tagger_id)


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
        self.add_cleanup_files(tagger_id)
