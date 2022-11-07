import json
import os
import pathlib
import uuid
from io import BytesIO
from time import sleep
from typing import List

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.helper_functions import reindex_test_dataset, get_core_setting, get_minio_client, set_core_setting
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (TEST_FIELD, TEST_FIELD_CHOICE, TEST_KEEP_PLOT_FILES, TEST_MATCH_TEXT, TEST_QUERY,
                                   TEST_TAGGER_BINARY, TEST_VERSION_PREFIX, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerViewTests(APITransactionTestCase):

    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.list_url = reverse(f"{VERSION_NAMESPACE}:tagger-list", kwargs={"project_pk": self.project.pk})

        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.multitag_text_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/multitag_text/'

        # set vectorizer & classifier options
        self.vectorizer_opts = ('TfIdf Vectorizer',)
        self.classifier_opts = ('LinearSVC',)

        # list tagger_ids for testing. is populated during training test
        self.test_tagger_ids = []
        self.client.login(username='taggerOwner', password='pw')

        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_TAGGER_NAME"
        self.new_fact_value = "TEST_TAGGER_VALUE"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying taggers",
            "indices": [self.test_index_name],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])

        self.test_imported_binary_tagger_id = self.import_test_model(TEST_TAGGER_BINARY)

        self.minio_tagger_path = f"ttk_tagger_tests/{str(uuid.uuid4().hex)}/model.zip"
        self.minio_client = get_minio_client()
        self.bucket_name = get_core_setting("TEXTA_S3_BUCKET_NAME")


    def import_test_model(self, file_path: str):
        """Import models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.list_url}import_model/'
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
        self.assertTrue(isinstance(response.data["classes"], list))
        self.assertTrue(len(response.data["classes"]) >= 2)
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
        self.run_check_for_add_model_as_favorite_and_test_filtering_by_it()

        # Ordering here is important.
        self.run_simple_check_that_you_can_import_models_into_s3()
        self.run_simple_check_that_you_can_download_models_from_s3()

        self.run_check_for_downloading_model_from_s3_with_wrong_faulty_access_configuration()
        self.run_check_for_doing_s3_operation_while_its_disabled_in_settings()
        self.run_check_for_downloading_model_from_s3_that_doesnt_exist()

    def add_cleanup_files(self, tagger_id):
        tagger_object = Tagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)
        if tagger_object.embedding:
            self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)

    def tearDown(self) -> None:
        Tagger.objects.all().delete()
        ec = ElasticCore()
        res = ec.delete_index(self.test_index_copy)
        ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete apply_taggers test index {self.test_index_copy}", res)

        self.minio_client.remove_object(self.bucket_name, self.minio_tagger_path)


    def run_create_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger, and if a new Task gets created via the signal"""

        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                payload = {
                    "description": "TestTagger",
                    "query": json.dumps(TEST_QUERY),
                    "fields": TEST_FIELD_CHOICE,
                    "indices": [{"name": self.test_index_name}],
                    "vectorizer": vectorizer_opt,
                    "classifier": classifier_opt,
                    "maximum_sample_size": 500,
                    "negative_multiplier": 1.0,
                    "score_threshold": 0.1,
                    "stop_words": ["asdfghjkl"]
                }
                # procees to analyze result
                response = self.client.post(self.list_url, payload, format='json')
                print_output('test_create_tagger_training_and_task_signal:response.data', response.data)
                # Check if Tagger gets created
                self.assertEqual(response.status_code, status.HTTP_201_CREATED)
                created_tagger = Tagger.objects.get(id=response.data['id'])
                # add tagger to be tested
                self.test_tagger_ids.append(created_tagger.pk)
                # Check if not errors
                task_object = created_tagger.tasks.last()
                self.assertEqual(task_object.errors, '[]')
                # Remove tagger files after test is done
                self.add_cleanup_files(created_tagger.id)
                # Check if Task gets created via a signal
                self.assertTrue(task_object is not None)
                # Check if Tagger gets trained and completed
                self.assertEqual(task_object.status, Task.STATUS_COMPLETED)
                # Check if Tagger object contains classes
                self.assertTrue(isinstance(response.data["classes"], list))
                self.assertTrue(len(response.data["classes"]) == 2)

    def run_create_tagger_with_incorrect_fields(self):
        """Tests the endpoint for a new Tagger with incorrect field data (should give error)"""
        payload = {
            "description": "TestTagger",
            "query": json.dumps(TEST_QUERY),
            "indices": [{"name": self.test_index_name}],
            "fields": ["randomgibberishhhhhhhhhh"],
            "vectorizer": self.vectorizer_opts[0],
            "classifier": self.classifier_opts[0],
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
        }

        response = self.client.post(self.list_url, payload, format='json')
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
            "indices": [{"name": self.test_index_name}],
            "vectorizer": "Hashing Vectorizer",
            "classifier": "Logistic Regression",
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0
        }

        create_response = self.client.post(self.list_url, payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        created_tagger_id = create_response.data['id']
        created_tagger_url = f'{self.list_url}{created_tagger_id}/'
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
            "indices": [{"name": self.test_index_name}],
            "vectorizer": "Hashing Vectorizer",
            "classifier": "Logistic Regression",
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0
        }
        create_response = self.client.post(self.list_url, payload, format='json')
        print_output("empty_fields_response", create_response.data)
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)

    def run_put_on_tagger_instances(self, test_tagger_ids):
        """ Tests put response success for Tagger fields """
        payload = {
            "description": "PutTagger",
            "query": json.dumps(TEST_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "indices": [{"name": self.test_index_name}],
            "vectorizer": 'Hashing Vectorizer',
            "classifier": 'Logistic Regression',
            "maximum_sample_size": 1000,
            "negative_multiplier": 3.0,
        }
        for test_tagger_id in test_tagger_ids:
            tagger_url = f'{self.list_url}{test_tagger_id}/'
            put_response = self.client.put(tagger_url, payload, format='json')
            print_output("put_response", put_response.data)
            self.assertEqual(put_response.status_code, status.HTTP_200_OK)

    def run_tag_text(self, test_tagger_ids: List[int]):

        payloads = [{"text": "This is some test text for the Tagger Test"}, {"text": "test"}]

        """Tests the endpoint for the tag_text action"""
        for payload in payloads:
            for test_tagger_id in test_tagger_ids:
                tag_text_url = f'{self.list_url}{test_tagger_id}/tag_text/'
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
                tag_text_url = f'{self.list_url}{test_tagger_id}/tag_text/'
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
            tag_text_url = f'{self.list_url}{test_tagger_id}/tag_text/'
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
            tag_text_url = f'{self.list_url}{test_tagger_id}/tag_doc/'
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
            tag_text_url = f'{self.list_url}{test_tagger_id}/tag_doc/'
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
                "indices": [{"name": self.test_index_name}]
            }
            url = f'{self.list_url}{test_tagger_id}/tag_random_doc/'
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
                list_features_get_url = f'{self.list_url}{test_tagger_id}/list_features/?size=10'
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

                list_features_post_url = f'{self.list_url}{test_tagger_id}/list_features/'
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
            url = f'{self.list_url}{test_tagger_id}/stop_words/'
            response = self.client.get(url)
            print_output('run_stop_word_list:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('stop_words' in response.data)

    def run_stop_word_add_and_replace(self):
        """Tests the endpoint for the stop_word_add action"""
        for test_tagger_id in self.test_tagger_ids:
            url = f'{self.list_url}{test_tagger_id}/stop_words/'
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
        task_object = self.reindexer_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_to_index: waiting for reindexer task to finish, current status:', task_object.status)
            sleep(2)

        test_tagger_id = self.test_imported_binary_tagger_id
        url = f'{self.list_url}{test_tagger_id}/apply_to_index/'

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
        task_object = tagger_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_to_index: waiting for applying tagger task to finish, current status:', task_object.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_tagger_to_index:elastic aggerator results:", results)

        # Check if expected number of facts are added to the index
        self.assertTrue(results[self.new_fact_value] > 0)
        self.add_cleanup_files(test_tagger_id)

    def run_apply_tagger_to_index_invalid_input(self):
        """Tests applying tagger to index using apply_to_index endpoint with invalid input."""

        test_tagger_id = self.test_tagger_ids[0]
        url = f'{self.list_url}{test_tagger_id}/apply_to_index/'

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

        # Get basic information to check for previous tagger deletion after retraining has finished.
        tagger_orm: Tagger = Tagger.objects.get(pk=test_tagger_id)
        model_path = pathlib.Path(tagger_orm.model.path)
        print_output('test_model_retrain:assert that previous model doesnt exist', data=model_path.exists())
        self.assertTrue(model_path.exists())

        # Check if stop word present in features
        url = f'{self.list_url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT in feature_dict)
        # add stop word before retraining
        url = f'{self.list_url}{test_tagger_id}/stop_words/'
        payload = {"stop_words": [TEST_MATCH_TEXT], 'overwrite_existing': True}
        response = self.client.post(url, payload, format='json')
        # retrain tagger
        url = f'{self.list_url}{test_tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        print_output('test_model_retrain:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Ensure that previous tagger is deleted properly.
        print_output('test_model_retrain:assert that previous model doesnt exist', data=model_path.exists())
        self.assertFalse(model_path.exists())
        # Ensure that the freshly created model wasn't deleted.
        tagger_orm.refresh_from_db()
        self.assertNotEqual(tagger_orm.model.path, str(model_path))

        # Check if response data
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # Check if stop word NOT present in features
        url = f'{self.list_url}{test_tagger_id}/list_features/'
        response = self.client.get(url)
        feature_dict = {a['feature']: True for a in response.data['features']}
        self.assertTrue(TEST_MATCH_TEXT not in feature_dict)
        self.add_cleanup_files(test_tagger_id)

    def run_model_export_import(self):
        """Tests endpoint for model export and import"""
        test_tagger_id = self.test_tagger_ids[0]

        # retrieve model zip
        url = f'{self.list_url}{test_tagger_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.list_url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Test prediction with imported tagger
        imported_tagger_id = response.data['id']
        print_output('test_import_model:response.data', response.data)

        tagger = Tagger.objects.get(id=imported_tagger_id)

        tagger_model_dir = pathlib.Path(settings.RELATIVE_MODELS_PATH) / "tagger"
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
        tag_text_url = f'{self.list_url}{tagger_id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_doc_with_feedback:response.data', response.data)
        self.assertTrue('feedback' in response.data)

        # generate feedback
        fb_id = response.data['feedback']['id']
        feedback_url = f'{self.list_url}{tagger_id}/feedback/'
        payload = {"feedback_id": fb_id, "correct_result": "True"}
        response = self.client.post(feedback_url, payload, format='json')
        print_output('test_tag_doc_with_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # sleep for a sec to allow elastic to finish its bussiness
        sleep(1)

        # list feedback
        feedback_list_url = f'{self.list_url}{tagger_id}/feedback/'
        response = self.client.get(feedback_list_url)
        print_output('test_tag_doc_list_feedback:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data)
        self.assertTrue(len(response.data) > 0)

        # retrain model
        url = f'{self.list_url}{tagger_id}/retrain_tagger/'
        response = self.client.post(url)
        # test tagging again for this model
        payload = {
            "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"})
        }
        tag_text_url = f'{self.list_url}{tagger_id}/tag_doc/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_feedback_retrained_tag_doc:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('result' in response.data)
        self.assertTrue('probability' in response.data)

        # delete feedback
        feedback_delete_url = f'{self.list_url}{tagger_id}/feedback/'
        response = self.client.delete(feedback_delete_url)
        print_output('test_tag_doc_delete_feedback:response.data', response.data)
        # sleep for a sec to allow elastic to finish its business
        sleep(1)

        # list feedback again to make sure its emtpy
        feedback_list_url = f'{self.list_url}{tagger_id}/feedback/'
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

    def test_tagger_with_only_description_input(self):
        payload = {"description": "TestTagger"}
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_tagger_with_only_description_input:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data["fields"][0] == "This field is required.")

    # Since this functionality is implemented by subclasses, the other apps should be covered by this test alone.
    def run_check_for_add_model_as_favorite_and_test_filtering_by_it(self):
        tagger_id = self.test_tagger_ids[0]

        url = reverse("v2:tagger-add-favorite", kwargs={"project_pk": self.project.pk, "pk": tagger_id})
        response = self.client.post(url, data={}, format="json")
        print_output("test_add_model_as_favorite_and_test_filtering_by_it:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(Tagger.objects.get(pk=tagger_id).favorited_users.filter(pk=self.user.pk).exists())

        # Check that filter works when looking for favorited things.
        response = self.client.get(self.list_url, data={"is_favorited": True})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["count"] == 1)

        # Check that not searching it with false doesn't break anything.
        response = self.client.get(self.list_url, data={"is_favorited": False})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["count"] != 1)

        # Check that removing the user works.
        response = self.client.post(url, data={}, format="json")
        self.assertFalse(Tagger.objects.get(pk=tagger_id).favorited_users.filter(pk=self.user.pk).exists())

    def test_that_ordering_and_filtering_by_new_task_format_works(self):
        payload = {
            "description": "abadaba",
            "fact_name": "TEEMA",
            "indices": [{"name": self.test_index_name}],
            "fields": [TEST_FIELD]
        }

        to_be_retrained_tagger_response = self.client.post(self.list_url, data=payload, format="json")
        self.assertEqual(to_be_retrained_tagger_response.status_code, status.HTTP_201_CREATED)
        to_be_retrained_tagger_id = to_be_retrained_tagger_response.data["id"]

        just_trained_tagger_response = self.client.post(self.list_url, data=payload, format="json")
        self.assertEqual(just_trained_tagger_response.status_code, status.HTTP_201_CREATED)
        just_trained_tagger_id = just_trained_tagger_response.data["id"]

        # Assert that there are two taggers trained.
        list_response = self.client.get(self.list_url)
        self.assertTrue(list_response.data["count"], 2)

        # Assert that filter based on status works.
        filtered_list_response = self.client.get(self.list_url, data={"task_status": "started"})
        self.assertEqual(filtered_list_response.data["count"], 0)

        # Retrain the first tagger to have its latest task be later than the tagger that was trained second.
        retrain_url = reverse(f"{VERSION_NAMESPACE}:tagger-retrain-tagger", kwargs={
            "project_pk": self.project.pk, "pk": to_be_retrained_tagger_id
        })
        retrain_response = self.client.post(retrain_url, data={}, format="json")
        self.assertEqual(retrain_response.status_code, status.HTTP_200_OK)

        # Check that the retrained tagger is given first when ordering by task completion
        ordered_list = self.client.get(self.list_url, data={"ordering": "-tasks__time_completed"})
        taggers = ordered_list.data["results"]
        self.assertEqual(taggers[0]["id"], to_be_retrained_tagger_id)

    def run_check_for_downloading_model_from_s3_that_doesnt_exist(self):
        url = reverse("v2:tagger-download-from-s3", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data={"minio_path": "this simply doesn't exist.zip"}, format="json")
        print_output("run_check_for_downloading_model_from_s3_that_doesnt_exist:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def run_check_for_downloading_model_from_s3_with_wrong_faulty_access_configuration(self):
        # THIS ABOMINATION REFUSES TO WORK
        # with override_settings(S3_ACCESS_KEY=uuid.uuid4().hex):
        #     response = self._run_s3_import(self.minio_tagger_path)
        #     print_output("run_check_for_downloading_model_from_s3_with_wrong_faulty_access_configuration-S3-ACCESS-KEY:response.data", response.data)
        #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        #
        # with override_settings(S3_SECRET_KEY=uuid.uuid4().hex):
        #     response = self._run_s3_import(self.minio_tagger_path)
        #     print_output("run_check_for_downloading_model_from_s3_with_wrong_faulty_access_configuration-S3-SECRET-KEY:response.data", response.data)
        #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        #
        # with override_settings(S3_BUCKET_NAME=uuid.uuid4().hex):
        #     response = self._run_s3_import(self.minio_tagger_path)
        #     print_output("run_check_for_downloading_model_from_s3_with_wrong_faulty_access_configuration-S3-BUCKET-NAME:response.data", response.data)
        #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        pass

    def run_check_for_doing_s3_operation_while_its_disabled_in_settings(self):
        set_core_setting("TEXTA_S3_ENABLED", "False")
        response = self._run_s3_import(self.minio_tagger_path)
        print_output("run_check_for_doing_s3_operation_while_its_disabled_in_settings:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("minio_path" in response.data)
        # Enable it again for the other tests.
        set_core_setting("TEXTA_S3_ENABLED", "True")

    def _run_s3_import(self, minio_path):
        url = reverse("v2:tagger-upload-into-s3", kwargs={"project_pk": self.project.pk, "pk": self.test_imported_binary_tagger_id})
        response = self.client.post(url, data={"minio_path": minio_path}, format="json")
        return response

    def run_simple_check_that_you_can_import_models_into_s3(self):
        response = self._run_s3_import(self.minio_tagger_path)
        print_output("run_simple_check_that_you_can_import_models_into_s3:response.data", response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check directly inside Minio whether the model exists there.
        exists = False
        for s3_object in self.minio_client.list_objects(self.bucket_name, recursive=True):
            if s3_object.object_name == self.minio_tagger_path:
                print_output(f"contents of minio:", s3_object.object_name)
                exists = True
                break
        self.assertEqual(exists, True)

        # Check that status is proper.
        t = Tagger.objects.get(pk=self.test_imported_binary_tagger_id)
        self.assertEqual(t.tasks.last().status, Task.STATUS_COMPLETED)
        self.assertEqual(t.tasks.last().task_type, Task.TYPE_UPLOAD)

    def run_simple_check_that_you_can_download_models_from_s3(self):
        url = reverse("v2:tagger-download-from-s3", kwargs={"project_pk": self.project.pk})
        latest_tagger_id = Tagger.objects.last().pk
        response = self.client.post(url, data={"minio_path": self.minio_tagger_path}, format="json")
        print_output("run_simple_check_that_you_can_download_models_from_s3:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        latest_again = Tagger.objects.last().pk

        # Assert that changes have happened.
        self.assertNotEqual(latest_tagger_id, latest_again)
        # Assert that you can tag with the imported tagger.
        self.run_tag_text([latest_again])
