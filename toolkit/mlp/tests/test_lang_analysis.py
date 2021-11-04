import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher
from toolkit.helper_functions import reindex_test_dataset
from toolkit.settings import NAN_LANGUAGE_TOKEN_KEY
from toolkit.test_settings import (TEST_FIELD, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class ApplyLangViewsTests(APITransactionTestCase):

    def setUp(self) -> None:
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('langDetectUser', 'my@email.com', 'pw')
        self.non_project_user = create_test_user('langDetectUserThatIsNotInProject', 'my@email.com', 'pw')
        self.project = project_creation("langDetectProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.client.login(username='langDetectUser', password='pw')
        self.url = reverse("v2:lang_index-list", kwargs={"project_pk": self.project.pk})


    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])


    def test_unauthenticated_project_access(self):
        self.client.logout()
        self.client.login(username="langDetectUserThatIsNotInProject", password="pw")
        response = self.client.get(self.url)
        print_output("test_unauthenticated_project_access:response.data", response.data)
        self.assertTrue(response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))


    def test_unauthenticated_view_access(self):
        self.client.logout()
        response = self.client.get(self.url)
        print_output("test_unauthenticated_view_access:response.data", response.data)
        self.assertTrue(response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))


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
        s = ElasticSearcher(indices=[self.test_index_name], output=ElasticSearcher.OUT_DOC, query=json.loads(payload["query"]))
        for hit in s:
            if TEST_FIELD in hit:
                self.assertTrue(f"{mlp_field}.language.detected" in hit)
                lang_value = hit[f"{mlp_field}.language.detected"]
                self.assertTrue(lang_value == "et")


    def test_applying_lang_detect_with_raw_query(self):
        mlp_field = f"{TEST_FIELD}_mlp"
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": {'query': {'match': {'comment_content_lemmas': query_string}}}
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_applying_lang_detect_with_raw_query:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


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


    def test_with_invalid_queries(self):
        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": "foo"
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_with_invalid_queries_v2:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)

        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": json.dumps("foo")
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_with_invalid_queries_v2:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_that_lang_detect_enters_nan_token_on_bogus_fields(self):
        # Set up the index with the target document that ensures NAN response.
        ec = ElasticCore()
        query_string = 159784984949
        document_id = "test_that_lang_detect_enters_nan_token_on_bogus_fields"
        ec.es.index(index=self.test_index_name, id=document_id, body={TEST_FIELD: query_string}, refresh="wait_for")

        payload = {
            "description": "TestingIndexProcessing",
            "field": TEST_FIELD,
            "query": json.dumps({'query': {'match': {TEST_FIELD: query_string}}}, ensure_ascii=False)
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_that_lang_detect_enters_nan_token_on_bogus_fields:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        s = ElasticSearcher(indices=[self.test_index_name], output=ElasticSearcher.OUT_DOC, query=json.loads(payload["query"]))
        for hit in s:
            self.assertTrue(hit[f"{TEST_FIELD}_mlp.language.detected"] == NAN_LANGUAGE_TOKEN_KEY)
            break

        # Clean up the document from the index.
        ec.es.delete(index=self.test_index_name, id=document_id, refresh="wait_for")


class TestLangDetectView(APITransactionTestCase):

    def setUp(self) -> None:
        self.normal_user = create_test_user('langDetectUser', 'my@email.com', 'pw')
        self.admin_user = create_test_user("langDetectAdmin", 'my@email.com', 'pw', superuser=True)
        self.client.login(username='langDetectUser', password='pw')
        self.text = "Kohus peatas põlevkiviõlitehase ehituse"
        self.url = reverse(f"{VERSION_NAMESPACE}:mlp_detect_lang")


    def test_normal_endpoint(self):
        response = self.client.post(self.url, data={"text": self.text}, format="json")
        print_output("test_normal_endpoint:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["language"] == "estonian")


    def test_faulty_text_content(self):
        smiley_face = ":)"
        response = self.client.post(self.url, data={"text": smiley_face}, format="json")
        print_output("test_faulty_text_content:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_that_unlogged_users_get_403(self):
        self.client.logout()
        response = self.client.post(self.url, data={"text": self.text}, format="json")
        print_output("test_that_unlogged_users_get_403:response.data", response.data)
        self.assertTrue(response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))


    def test_that_normal_users_have_access(self):
        self.client.logout()
        self.client.login(username="langDetectAdmin", password='pw')
        response = self.client.post(self.url, data={"text": self.text}, format="json")
        print_output("test_that_normal_users_have_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["language"] == "estonian")


    def test_blank_user_input(self):
        response = self.client.post(self.url, data={"text": ""}, format="json")
        print_output("test_blank_user_input:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_that_unsupported_snowball_lang_gets_long_as_null(self):
        response = self.client.post(self.url, data={"text": "音読み"}, format="json")
        print_output("test_that_unsupported_snowball_lang_gets_long_as_null:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["language"] is None)
