import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.embedding.models import Embedding
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import (TEST_FIELD_CHOICE, TEST_QUERY, TEST_RAKUN_QUERY, TEST_VERSION_PREFIX, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class RakunViewTest(APITransactionTestCase):
    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("RakunExtractorTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/'
        self.embedding_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'

        self.rakun_id = None
        self.client.login(username='user', password='pw')

        self.new_stopwords = ["New_word1", "New_word2"]

        """Create FastText Embedding, which will save facebook_model"""
        fasttext_payload = {
            "description": "TestEmbedding",
            "query": json.dumps(TEST_QUERY),
            "indices": [{"name": self.test_index_name}],
            "fields": TEST_FIELD_CHOICE,
            "embedding_type": "FastTextEmbedding"
        }
        print_output("Staring Rakun fasttext embedding", "post")

        response = self.client.post(self.embedding_url, json.dumps(fasttext_payload), content_type='application/json')
        print_output('test_create_rakun_fasttext_embedding_training_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_embedding_id = created_embedding.id
        # Remove Embedding files after test is done
        task_object = created_embedding.tasks.last()
        print_output("created Rakun fasttext embedding task status", task_object.status)
        # Check if Task gets created via a signal
        self.assertTrue(task_object is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(task_object.status, Task.STATUS_COMPLETED)

        self.ids = []
        self.payloads = [
            {
                "description": "test_all",
                "distance_method": "fasttext",
                "distance_threshold": 1,
                "num_keywords": 1,
                "pair_diff_length": 1,
                "stopwords": ["word1", "word2"],
                "bigram_count_threshold": 2,
                "min_tokens": 1,
                "max_tokens": 2,
                "max_similar": 2,
                "max_occurrence": 2,
                "fasttext_embedding": self.test_embedding_id
            },
            {
                "description": "rakun_test_new",
                "distance_method": "fasttext",
                "distance_threshold": 1.0,
                "min_tokens": 1,
                "max_tokens": 2,
                "fasttext_embedding": self.test_embedding_id
            }
        ]

        rakun_url = reverse(f"{VERSION_NAMESPACE}:rakun_extractor-list", kwargs={"project_pk": self.project.pk})
        for payload in self.payloads:
            response = self.client.post(rakun_url, payload)
            self.assertTrue(response.status_code == status.HTTP_201_CREATED)
            self.ids.append(int(response.data["id"]))


    def tearDown(self) -> None:
        ec = ElasticCore()
        ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete [Rakun Extractor] test index {self.test_index_name}", None)
        Embedding.objects.all().delete()
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete Rakun FASTTEXT Embeddings", None)


    def test(self):
        self.run_test_apply_rakun_extractor_to_index()
        self.run_test_rakun_extractor_duplicate()
        self.run_test_rakun_extractor_from_random_doc()
        self.run_test_rakun_extractor_from_text()
        self.run_test_rakun_extractor_stopwords()
        self.run_test_rakun_extractor_edit()
        self.run_check_that_patch_doesnt_delete_stopwords()


    def run_test_apply_rakun_extractor_to_index(self):
        index_payload = {
            "indices": [{"name": self.test_index_name}],
            "description": "test_apply_rakun_to_index",
            "fields": TEST_FIELD_CHOICE,
            "query": json.dumps(TEST_RAKUN_QUERY)
        }
        for rakun_id in self.ids:
            rakun_apply_to_index_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{rakun_id}/apply_to_index/'
            response = self.client.post(rakun_apply_to_index_url, index_payload)
            print_output(f"Apply Rakun to Index for ID: {rakun_id}", response.json())
            self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def run_test_rakun_extractor_duplicate(self):
        duplicate_payload = {}
        for rakun_id in self.ids:
            rakun_duplicate_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{rakun_id}/duplicate/'
            response = self.client.post(rakun_duplicate_url, duplicate_payload)
            print_output(f"Duplicate Rakun for ID: {rakun_id}", response.json())
            self.assertTrue(response.status_code == status.HTTP_200_OK)


    def run_test_rakun_extractor_from_random_doc(self):
        random_payload = {
            "indices": [{"name": self.test_index_name}],
            "fields": TEST_FIELD_CHOICE
        }
        for rakun_id in self.ids:
            rakun_random_doc_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{rakun_id}/extract_from_random_doc/'
            response = self.client.post(rakun_random_doc_url, random_payload)
            print_output(f"Rakun extract from random doc for ID: {rakun_id}", response.json())
            self.assertTrue(response.status_code == status.HTTP_200_OK)


    def run_test_rakun_extractor_from_text(self):
        text_payload = {
            "text": "This is some random text to be used with Rakun."
        }
        for rakun_id in self.ids:
            rakun_text_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{rakun_id}/extract_from_text/'
            response = self.client.post(rakun_text_url, text_payload)
            print_output(f"Rakun extract from text for ID: {rakun_id}", response.json())
            self.assertTrue(response.status_code == status.HTTP_200_OK)


    def run_test_rakun_extractor_stopwords(self):
        stopwords_payload = {
            "stopwords": ["Word1", "Word2"],
            "overwrite_existing": False
        }
        for rakun_id in self.ids:
            rakun_stopwords_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{rakun_id}/stop_words/'
            response = self.client.post(rakun_stopwords_url, stopwords_payload)
            print_output(f"Rakun stopwords for ID: {rakun_id}", response.json())
            self.assertTrue(response.status_code == status.HTTP_200_OK)


    def run_test_rakun_extractor_edit(self):
        rakun_extractor_edit_payload = {
            "description": "test_edit",
            "stopwords": self.new_stopwords
        }
        for rakun_id in self.ids:
            rakun_edit_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{rakun_id}/'
            response = self.client.put(rakun_edit_url, rakun_extractor_edit_payload)
            print_output(f"Editing Rakun Extractor for ID: {rakun_id}", response.json())
            self.assertTrue(response.status_code == status.HTTP_200_OK)


    def run_check_that_patch_doesnt_delete_stopwords(self):
        url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{self.ids[0]}/'
        response = self.client.patch(url, data={"description": "hello there"}, format="json")
        print_output("run_check_that_patch_doesnt_delete_stopwords:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        stopwords_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/rakun_extractors/{self.ids[0]}/stop_words/'
        stopwords_response = self.client.get(stopwords_url, format="json")
        stopwords = stopwords_response.data["stopwords"]
        self.assertTrue(stopwords == self.payloads[0]["stopwords"] or stopwords == ["New_word1", "New_word2"])
