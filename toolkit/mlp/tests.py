# Create your tests here.
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from toolkit.elastic.searcher import ElasticSearcher
from toolkit.test_settings import (TEST_FIELD, TEST_INDEX)
from toolkit.tools.utils_for_tests import create_test_user, project_creation


class MLPListsTests(APITestCase):


    def setUp(self):
        self.user = create_test_user('mlpUser', 'my@email.com', 'pw')
        self.project = project_creation("mlpTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='mlpUser', password='pw')
        self.url = reverse("v1:mlp_texts")
        self.payload = {
            "texts": [
                "Õnnetus leidis aset eile kella 17.25 ajal Raplamaal Märjamaa alevis Koluvere maantee 2 juures, kus alkoholijoobes 66-aastane mees sõitis mopeedautoga Bellier 503 ringristmikul teelt välja vastu liiklusmärki.",
                "Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic",
                "Приложение №1 для заботы о здоровье бесплатно по полису ОМС."
            ]
        }

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_normal_call(self):
        response = self.client.post(self.url, data=self.payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        for doc in response.data:
            mlp = doc["text"]
            self.assertTrue("texta_facts" in doc)
            self.assertTrue("text" in mlp and mlp["text"])
            self.assertTrue("lemmas" in mlp and mlp["lemmas"])
            self.assertTrue("pos_tags" in mlp and mlp["pos_tags"])
            self.assertTrue("lang" in mlp and mlp["lang"])

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_fact_processing(self):
        response = self.client.post(self.url, data={"texts": ["Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic, and Donald Trump countering by calling him ‘grossly incompetent’."]},
                                    format="json")
        for doc in response.data:
            self.assertTrue(response.status_code == status.HTTP_200_OK)
            self.assertTrue(len(doc["texta_facts"]) > 0)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_separate_analyzer_handling(self):
        response = self.client.post(self.url, data={**self.payload, "analyzers": ["lemmas"]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        demanded_keys = ["text", "lemmas", "lang"]
        for doc in response.data:
            mlp = doc["text"]
            for key in mlp.keys():
                self.assertTrue(key in demanded_keys)


class MLPDocsTests(APITestCase):


    def setUp(self):
        self.user = create_test_user('mlpUser', 'my@email.com', 'pw')
        self.project = project_creation("mlpTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='mlpUser', password='pw')
        self.url = reverse("v1:mlp_docs")
        self.payload = {
            "docs": [
                {"text": "Õnnetus leidis aset eile kella 17.25 ajal Raplamaal Märjamaa alevis Koluvere maantee 2 juures, kus alkoholijoobes 66-aastane mees sõitis mopeedautoga Bellier 503 ringristmikul teelt välja vastu liiklusmärki."},
                {"text": "Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic", },
                {"text": "Приложение №1 для заботы о здоровье бесплатно по полису ОМС."}
            ],
            "fields_to_parse": ["text"]
        }

    @override_settings(CELERY_ALWAYS_EAGER=True)
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
                self.assertTrue("lang" in mlp and mlp["lang"])

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_fact_processing(self):
        docs = [{"text": "Ex- US President Barack Obama and his successor recently exchanged verbal barbs, with the former slamming the administration’s handling of the COVID-19 pandemic"}]
        fields_to_parse = ["text"]
        response = self.client.post(self.url, format="json", data={"docs": docs, "fields_to_parse": fields_to_parse})
        for document in response.data:
            self.assertTrue("texta_facts" in document)
            self.assertTrue(len(document["texta_facts"]) > 0)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_separate_analyzer_handling(self):
        response = self.client.post(self.url, format="json", data={**self.payload, "analyzers": ["lemmas"]})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        demanded_keys = ["text", "lemmas", "lang"]
        mlp_keys = [f"{key}_mlp" for key in self.payload["fields_to_parse"]]
        for doc in response.data:
            for mlp_field_key in mlp_keys:
                mlp = doc[mlp_field_key]
                for field_name in mlp.keys():
                    self.assertTrue(field_name in demanded_keys)

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_nested_path_handling(self):
        payload = {"docs": [{"text": {"text": "Tere maailm, ma olen veebis~!"}}], "fields_to_parse": ["text.text"]}
        response = self.client.post(self.url, data=payload, format="json")
        for doc in response.data:
            key_to_parse: str = payload["fields_to_parse"][0]
            keys = key_to_parse.split(".")
            mlp = doc[keys[0]][f"{keys[1]}_mlp"]

            self.assertTrue("texta_facts" in doc)
            self.assertTrue("text" in mlp and mlp["text"])
            self.assertTrue("lemmas" in mlp and mlp["lemmas"])
            self.assertTrue("pos_tags" in mlp and mlp["pos_tags"])
            self.assertTrue("lang" in mlp and mlp["lang"])


class MLPIndexProcessing(APITransactionTestCase):


    def setUp(self):
        self.user = create_test_user('mlpUser', 'my@email.com', 'pw')
        self.project = project_creation("mlpTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='mlpUser', password='pw')
        self.url = reverse("v1:mlp-list", kwargs={"project_pk": self.project.pk})

    @override_settings(CELERY_ALWAYS_EAGER=True)
    def test_index_processing(self):
        query_string = "inimene"
        payload = {
            "description": "TestingIndexProcessing",
            "fields": [TEST_FIELD],
            "query": {'query': {'match': {'comment_content_lemmas': query_string}}}
        }

        response = self.client.post(self.url, data=payload, format="json")

        # Check if MLP was applied to the documents properly.
        mlp_field = f"{TEST_FIELD}_mlp"
        s = ElasticSearcher(indices=[TEST_INDEX], output=ElasticSearcher.OUT_DOC, query=payload["query"])
        for hit in s:
            if TEST_FIELD in hit:
                self.assertTrue(f"{TEST_FIELD}_mlp.lemmas" in hit)
                self.assertTrue(f"{TEST_FIELD}_mlp.pos_tags" in hit)
                self.assertTrue(f"{TEST_FIELD}_mlp.text" in hit)
                self.assertTrue(f"{TEST_FIELD}_mlp.lang" in hit)

                self._check_for_if_query_correct(hit, TEST_FIELD, query_string)


    def _check_for_if_query_correct(self, hit: dict, field_name: str, query_string: str):
        text = hit[field_name]
        self.assertTrue(query_string in text)
