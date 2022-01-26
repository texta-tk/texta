import json
import time
from unittest import skipIf

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from texta_elastic.core import ElasticCore
from toolkit.helper_functions import reindex_test_dataset
from toolkit.tagger.models import Tagger
from toolkit.test_settings import (TEST_FIELD, TEST_QUERY, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


def skip_for_es6():
    ec = ElasticCore()
    first, second, third = ec.get_version()
    if first == 7:
        return False
    else:
        return True


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerSnowballStemmerTests(APITransactionTestCase):

    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.client.login(username='taggerOwner', password='pw')


    def tearDown(self) -> None:
        Tagger.objects.all().delete()
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])


    def _apply_lang_detect_to_index(self):
        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": json.dumps(TEST_QUERY, ensure_ascii=False)
        }
        url = reverse(f"{VERSION_NAMESPACE}:lang_index-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("_apply_lang_detect_to_index:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_that_detect_lang_and_snowball_language_are_mutually_exclusive(self):
        payload = {
            "description": "TestTagger",
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "classifier": "LinearSVC",
            "maximum_sample_size": 500,
            "query": json.dumps(TEST_QUERY, ensure_ascii=False),
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "detect_lang": True,
            "snowball_language": "estonian"
        }
        url = reverse(f"{VERSION_NAMESPACE}:tagger-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_that_detect_lang_and_snowball_language_are_mutually_exclusive:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    @skipIf(skip_for_es6(), "This test only works for ES7 which has an Estonian stemmer!")
    def test_running_snowball_stemmer_with_predefined_language(self):
        payload = {
            "description": "TestTagger",
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "classifier": "LinearSVC",
            "query": json.dumps(TEST_QUERY, ensure_ascii=False),
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "snowball_language": "estonian"
        }
        url = reverse(f"{VERSION_NAMESPACE}:tagger-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_running_snowball_stemmer_with_predefined_language:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    @skipIf(skip_for_es6(), "This test only works for ES7 which has an Estonian stemmer!")
    def test_training_tagger_with_snowball_stemmer_that_detects_lang_from_documents(self):
        self._apply_lang_detect_to_index()
        time.sleep(10)
        payload = {
            "description": "TestTagger",
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "classifier": "LinearSVC",
            "query": json.dumps(TEST_QUERY, ensure_ascii=False),
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "detect_lang": True
        }
        url = reverse(f"{VERSION_NAMESPACE}:tagger-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_training_tagger_with_snowball_stemmer_that_detects_lang_from_documents:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_running_snowball_stemmer_with_a_wrong_language_value(self):
        payload = {
            "description": "TestTagger",
            "fields": [TEST_FIELD],
            "vectorizer": "TfIdf Vectorizer",
            "classifier": "LinearSVC",
            "query": json.dumps(TEST_QUERY, ensure_ascii=False),
            "maximum_sample_size": 500,
            "negative_multiplier": 1.0,
            "score_threshold": 0.1,
            "snowball_language": "nonexistent_language"
        }
        url = reverse(f"{VERSION_NAMESPACE}:tagger-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_running_snowball_stemmer_with_predefined_language_but_the_wrong_language:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
