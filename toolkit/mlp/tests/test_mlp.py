# Create your tests here.
import json
import uuid

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from toolkit.elastic.index.models import Index
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import (TEST_FIELD, TEST_INDEX, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


DOCTYPE_INDEX_NAME = "test_index_two"
DOCTYPE_FIELD_NAME = "sample_field"


@override_settings(CELERY_ALWAYS_EAGER=True)
class MLPListsTests(APITestCase):


    def setUp(self):
        self.user = create_test_user('mlpUser', 'my@email.com', 'pw')
        self.project = project_creation("mlpTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='mlpUser', password='pw')
        self.url = reverse(f"{VERSION_NAMESPACE}:mlp_texts")
        self.payload = {
            "texts": [
                "Õnnetus leidis aset eile kella 17.25 ajal Raplamaal Märjamaa alevis Koluvere maantee 2 juures, kus alkoholijoobes 66-aastane mees sõitis mopeedautoga Bellier 503 ringristmikul teelt välja vastu liiklusmärki.",
                "Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic",
                "Приложение №1 для заботы о здоровье бесплатно по полису ОМС."
            ]
        }


    def test_normal_call(self):
        response = self.client.post(self.url, data=self.payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        for doc in response.data:
            mlp = doc["text_mlp"]
            self.assertTrue("texta_facts" in doc)
            self.assertTrue("text" in mlp and mlp["text"])
            self.assertTrue("lemmas" in mlp and mlp["lemmas"])
            self.assertTrue("pos_tags" in mlp and mlp["pos_tags"])
            self.assertTrue("language" in mlp and mlp["language"])


    def test_fact_processing(self):
        response = self.client.post(self.url, data={"texts": ["Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic, and Donald Trump countering by calling him ‘grossly incompetent’."]},
                                    format="json")
        for doc in response.data:
            self.assertTrue(response.status_code == status.HTTP_200_OK)
            self.assertTrue(len(doc["texta_facts"]) > 0)


    def test_separate_analyzer_handling(self):
        response = self.client.post(self.url, data={**self.payload, "analyzers": ["lemmas"]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        demanded_keys = ["text", "lemmas", "language"]
        for doc in response.data:
            mlp = doc["text_mlp"]
            for key in mlp.keys():
                self.assertTrue(key in demanded_keys)


@override_settings(CELERY_ALWAYS_EAGER=True)
class MLPDocsTests(APITestCase):


    def setUp(self):
        self.user = create_test_user('mlpUser', 'my@email.com', 'pw')
        self.project = project_creation("mlpTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='mlpUser', password='pw')
        self.url = reverse(f"{VERSION_NAMESPACE}:mlp_docs")
        self.payload = {
            "docs": [
                {"text": "Õnnetus leidis aset eile kella 17.25 ajal Raplamaal Märjamaa alevis Koluvere maantee 2 juures, kus alkoholijoobes 66-aastane mees sõitis mopeedautoga Bellier 503 ringristmikul teelt välja vastu liiklusmärki."},
                {"text": "Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic"},
                {"text": "Приложение №1 для заботы о здоровье бесплатно по полису ОМС."}
            ],
            "fields_to_parse": ["text"]
        }


    def test_normal_call(self):
        response = self.client.post(self.url, format="json", data=self.payload)
        for doc in response.data:
            mlp_keys = [f"{key}_mlp" for key in self.payload["fields_to_parse"]]
            for key in mlp_keys:
                self.assertTrue(key in doc)
                mlp = doc[key]
                self.assertTrue("texta_facts" in doc)
                self.assertTrue("text" in mlp and mlp["text"])
                self.assertTrue("lemmas" in mlp and mlp["lemmas"])
                self.assertTrue("pos_tags" in mlp and mlp["pos_tags"])
                self.assertTrue("language" in mlp and mlp["language"])


    def test_fact_processing(self):
        docs = [{"text": "Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic"}]
        fields_to_parse = ["text"]
        response = self.client.post(self.url, format="json", data={"docs": docs, "fields_to_parse": fields_to_parse})
        for document in response.data:
            self.assertTrue("texta_facts" in document)
            self.assertTrue(len(document["texta_facts"]) > 0)


    def test_separate_analyzer_handling(self):
        response = self.client.post(self.url, format="json", data={**self.payload, "analyzers": ["lemmas"]})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        demanded_keys = ["text", "lemmas", "language"]
        mlp_keys = [f"{key}_mlp" for key in self.payload["fields_to_parse"]]
        for doc in response.data:
            for mlp_field_key in mlp_keys:
                mlp = doc[mlp_field_key]
                for field_name in mlp.keys():
                    self.assertTrue(field_name in demanded_keys)


    def test_nested_path_handling(self):
        payload = {"docs": [{"text": {"text": "Tere maailm, ma olen veebis~!"}}], "fields_to_parse": ["text.text"]}
        response = self.client.post(self.url, data=payload, format="json")
        for doc in response.data:
            key_to_parse = payload["fields_to_parse"][0]
            keys = key_to_parse.split(".")
            mlp = doc[keys[0]][f"{keys[1]}_mlp"]

            self.assertTrue("texta_facts" in doc)
            self.assertTrue("text" in mlp and mlp["text"])
            self.assertTrue("lemmas" in mlp and mlp["lemmas"])
            self.assertTrue("pos_tags" in mlp and mlp["pos_tags"])
            self.assertTrue("language" in mlp and mlp["language"])


@override_settings(CELERY_ALWAYS_EAGER=True)
class MLPIndexProcessing(APITransactionTestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.ec = ElasticCore()
        self.user = create_test_user('mlpUser', 'my@email.com', 'pw')
        self.project = project_creation("mlpTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.client.login(username='mlpUser', password='pw')
        self.url = reverse(f"{VERSION_NAMESPACE}:mlp_index-list", kwargs={"project_pk": self.project.pk})


    def tearDown(self) -> None:
        self.ec.delete_index(self.test_index_name, ignore=[400, 404])


    def _assert_mlp_contents(self, hit: dict, test_field: str):
        self.assertTrue(f"{test_field}_mlp.lemmas" in hit)
        self.assertTrue(f"{test_field}_mlp.pos_tags" in hit)
        self.assertTrue(f"{test_field}_mlp.text" in hit)
        self.assertTrue(f"{test_field}_mlp.language.analysis" in hit)
        self.assertTrue(f"{test_field}_mlp.language.detected" in hit)


    def test_index_processing(self):
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "fields": [TEST_FIELD],
            "query": json.dumps({'query': {'match': {'comment_content_lemmas': query_string}}}, ensure_ascii=False)
        }

        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_index_processing:response.data", response.data)

        # Check if MLP was applied to the documents properly.
        s = ElasticSearcher(indices=[self.test_index_name], output=ElasticSearcher.OUT_DOC, query=payload["query"])
        for hit in s:
            self._assert_mlp_contents(hit, TEST_FIELD)


    def _check_for_if_query_correct(self, hit: dict, field_name: str, query_string: str):
        text = hit[field_name]
        self.assertTrue(query_string in text)


    def test_payload_without_fields_value(self):
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "query": json.dumps({'query': {'match': {'comment_content_lemmas': query_string}}}, ensure_ascii=False)
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_payload_without_fields_value:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data["fields"][0] == "This field is required.")


    def test_payload_with_empty_fields_value(self):
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "query": json.dumps({'query': {'match': {'comment_content_lemmas': query_string}}}, ensure_ascii=False),
            "fields": []
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_payload_without_fields_value:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data["fields"][0] == "This list may not be empty.")


    def test_payload_with_invalid_field_value(self):
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "fields": ["this_field_does_not_exist"],
            "query": json.dumps({'query': {'match': {'comment_content_lemmas': query_string}}}, ensure_ascii=False)
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_payload_with_invalid_field_value:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_applying_mlp_on_two_indices(self):
        query_string = "inimene"
        indices = [f"texta_test_{uuid.uuid1()}", f"texta_test_{uuid.uuid1()}"]
        for index in indices:
            self.ec.es.indices.create(index=index, ignore=[400, 404])
            self.ec.es.index(index=index, body={"text": "obscure content to parse!"})
            index, is_created = Index.objects.get_or_create(name=index)
            self.project.indices.add(index)

        payload = {
            "description": "TestingIndexProcessing",
            "fields": ["text"],
            "indices": [{"name": index} for index in indices],
            "query": json.dumps({'query': {'match': {'comment_content_lemmas': query_string}}}, ensure_ascii=False)
        }
        response = self.client.post(self.url, data=payload, format="json")
        print_output("test_applying_mlp_on_two_indices:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        for index in indices:
            self.ec.es.indices.delete(index=index, ignore=[400, 404])
