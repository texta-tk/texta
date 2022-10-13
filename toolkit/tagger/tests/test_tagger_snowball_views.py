from typing import List

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.helper_functions import reindex_test_dataset
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (TEST_FIELD_UNLEMMATIZED_CHOICE, TEST_KEEP_PLOT_FILES, TEST_VERSION_PREFIX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerViewTests(APITransactionTestCase):


    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.multitag_text_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/taggers/multitag_text/'

        # set vectorizer & classifier options
        self.vectorizer_opts = ('Count Vectorizer',)
        self.classifier_opts = ('Logistic Regression',)

        self.snowball_languages = (
            # 'english',
            # 'finnish',
            'estonian',
        )

        # list tagger_ids for testing. is populated during training test
        self.test_tagger_ids = []
        self.client.login(username='taggerOwner', password='pw')


    def test_run(self):
        self.run_create_snowball_tagger_training_and_task_signal()
        self.run_snowball_tag_text(self.test_tagger_ids)
        self.run_snowball_list_features(self.test_tagger_ids)


    def add_cleanup_files(self, tagger_id):
        tagger_object = Tagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)
        if tagger_object.embedding:
            self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)


    def tearDown(self) -> None:
        Tagger.objects.all().delete()
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])


    def run_create_snowball_tagger_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger, and if a new Task gets created via the signal"""
        for vectorizer_opt in self.vectorizer_opts:
            for classifier_opt in self.classifier_opts:
                for snowball_language in self.snowball_languages:
                    payload = {
                        "description": "TestTaggerSnowball",
                        "fields": TEST_FIELD_UNLEMMATIZED_CHOICE,
                        "vectorizer": vectorizer_opt,
                        "classifier": classifier_opt,
                        "maximum_sample_size": 500,
                        "negative_multiplier": 1.0,
                        "score_threshold": 0.1,
                        "snowball_language": snowball_language
                    }
                    # procees to analyze result
                    response = self.client.post(self.url, payload, format='json')
                    print_output('test_create_snowball_tagger_training_and_task_signal:response.data', response.data)
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


    def run_snowball_list_features(self, test_tagger_ids: List[int]):
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
                # Check if any features listed
                self.assertTrue(len(response.data['features']) > 0)


    def run_snowball_tag_text(self, test_tagger_ids: List[int]):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "This is some test text for the Tagger Test"}
        for test_tagger_id in test_tagger_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_snowball_tag_text:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue('result' in response.data)
            self.assertTrue('probability' in response.data)
