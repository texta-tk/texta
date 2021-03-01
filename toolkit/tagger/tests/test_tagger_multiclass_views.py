import json
import os
import pathlib
import uuid
from io import BytesIO
from time import sleep
from typing import List

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.elastic.tools.models import Reindexer
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (TEST_FIELD,
                                   TEST_FIELD_CHOICE,
                                   TEST_FACT_NAME,
                                   TEST_INDEX,
                                   TEST_QUERY,
                                   TEST_VERSION_PREFIX,
                                   TEST_KEEP_PLOT_FILES
                                   )
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
        self.new_fact_name = "TEST_MULTICLASS_TAGGER_NAME"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_multiclass_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying multiclass taggers",
            "indices": [TEST_INDEX],
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying multiclass tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])


    def test_run(self):
        self.run_create_multiclass_tagger_training_and_task_signal()
        self.run_multiclass_tag_text(self.test_tagger_ids)
        self.run_apply_multiclass_tagger_to_index()
        self.run_apply_mutliclass_tagger_to_index_invalid_input()


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
        print_output(f"Delete apply_multiclass_taggers test index {self.test_index_copy}", res)


    def run_create_multiclass_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger, and if a new Task gets created via the signal"""
        # run test for multiclass training
        # run test for each vectorizer & classifier option
        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                payload = {
                    "description": "TestTaggerMultiClass",
                    "fields": TEST_FIELD_CHOICE,
                    "fact_name": TEST_FACT_NAME,
                    "vectorizer": vectorizer_opt,
                    "classifier": classifier_opt,
                    "maximum_sample_size": 500,
                    "negative_multiplier": 1.0,
                    "score_threshold": 0.1
                }
                # as lemmatization is slow, do it only once
                lemmatize = False
                # procees to analyze result
                response = self.client.post(self.url, payload, format='json')
                print_output('test_create_multiclass_tagger_training_and_task_signal:response.data', response.data)
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


    def run_multiclass_tag_text(self, test_tagger_ids: List[int]):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "This is some test text for the Tagger Test"}
        for test_tagger_id in test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_multiclass_tag_text:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('result' in response.data)
            self.assertTrue('probability' in response.data)


    def run_apply_multiclass_tagger_to_index(self):
        """Tests applying multiclass tagger to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_multiclass_tagger_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        test_tagger_id = self.test_tagger_ids[0]
        url = f'{self.url}{test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply multiclass tagger test task",
            "new_fact_name": self.new_fact_name,
            "indices": [{"name": self.test_index_copy}],
            "fields": TEST_FIELD_CHOICE,
            "query": json.dumps(TEST_QUERY),
            "lemmatize": False,
            "bulk_size": 100
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_multiclass_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = Tagger.objects.get(pk=test_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_mutliclass_tagger_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_multiclass_tagger_to_index:elastic aggerator results:", results)

        # Check if applying the tagger results in at least 1 new fact
        # Exact numbers cannot be checked as creating taggers contains random and thus
        # predicting with them isn't entirely deterministic
        self.assertTrue(len(results) >= 1)


    def run_apply_mutliclass_tagger_to_index_invalid_input(self):
        """Tests applying multiclass tagger to index using apply_to_index endpoint with invalid input."""

        test_tagger_id = self.test_tagger_ids[0]
        url = f'{self.url}{test_tagger_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "fields": "invalid_field_format",
            "lemmatize": False,
            "bulk_size": 100
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_to_index_invalid_input:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
