import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.settings import NAN_LANGUAGE_TOKEN_KEY
from toolkit.test_settings import (TEST_FIELD, TEST_INDEX)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class ApplyLangViewsTests(APITransactionTestCase):

    def setUp(self) -> None:
        self.user = create_test_user('langDetectUser', 'my@email.com', 'pw')
        self.non_project_user = create_test_user('langDetectUserThatIsNotInProject', 'my@email.com', 'pw')
        self.project = project_creation("langDetectProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='langDetectUser', password='pw')
        self.url = reverse("v2:lang_index-list", kwargs={"project_pk": self.project.pk})


    def test_unauthenticated_project_access(self):
        self.client.logout()
        self.client.login(username="langDetectUserThatIsNotInProject", password="pw")
        response = self.client.get(self.url)
        print_output("test_unauthenticated_project_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_unauthenticated_view_access(self):
        self.client.logout()
        response = self.client.get(self.url)
        print_output("test_unauthenticated_view_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_applying_lang_detect_with_query(self):
        mlp_field = f"{TEST_FIELD}_mlp"
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": json.dumps({'query': {'match': {'comment_content_lemmas': query_string}}}, ensure_ascii=False)
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_applying_lang_detect_with_query:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        s = ElasticSearcher(indices=[TEST_INDEX], output=ElasticSearcher.OUT_DOC, query=json.loads(payload["query"]))
        for hit in s:
            if TEST_FIELD in hit:
                self.assertTrue(f"{mlp_field}.language.detected" in hit)
                lang_value = hit[f"{mlp_field}.language.detected"]
                self.assertTrue(lang_value == "et")


    def test_applying_lang_detect_with_faulty_field_path(self):
        payload = {
            "description": "TestingIndexProcessing",
            "field": "not_an_valid_field_path",
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_applying_lang_detect_with_faulty_field_path:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_with_non_existing_indices_in_payload(self):
        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "indices": "index_that_does_not_exist_at_all"
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_with_non_existing_indices_in_payload:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_that_lang_detect_enters_nan_token_on_bogus_fields(self):
        # Set up the index with the target document that ensures NAN response.
        ec = ElasticCore()
        query_string = 159784984949
        document_id = "test_that_lang_detect_enters_nan_token_on_bogus_fields"
        ec.es.index(index=TEST_INDEX, id=document_id, body={TEST_FIELD: query_string}, refresh="wait_for")

        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": json.dumps({'query': {'match': {TEST_FIELD: query_string}}}, ensure_ascii=False)
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_that_lang_detect_enters_nan_token_on_bogus_fields:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        s = ElasticSearcher(indices=[TEST_INDEX], output=ElasticSearcher.OUT_DOC, query=json.loads(payload["query"]))
        for hit in s:
            self.assertTrue(hit[f"{TEST_FIELD}_mlp.language.detected"] == NAN_LANGUAGE_TOKEN_KEY)
            break

        # Clean up the document from the index.
        ec.es.delete(index=TEST_INDEX, id=document_id, refresh="wait_for")
