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
                                   TEST_FACT_NAME,
                                   TEST_INDEX,
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


    def test_run(self):
        self.run_create_multiclass_tagger_training_and_task_signal()
        self.run_multiclass_tag_text(self.test_tagger_ids)


    def tearDown(self) -> None:
        Tagger.objects.all().delete()


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
                self.addCleanup(remove_file, created_tagger.model.path)
                if not TEST_KEEP_PLOT_FILES:
                    self.addCleanup(remove_file, created_tagger.plot.path)
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
