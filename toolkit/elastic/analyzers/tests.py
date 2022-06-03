import json

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from texta_elastic.core import ElasticCore
from texta_elastic.searcher import ElasticSearcher
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_NESTED_FIELDS, TEST_QUERY, VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class SnowballElasticStemmerViewTest(APITestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("elasticSnowballStemmer", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='user', password='pw')


    def test_elastic_stemmer_on_english_text(self):
        url = reverse(f"{VERSION_NAMESPACE}:snowball")
        payload = {"text": "This is some text parsed by the english stemmer!", "language": "english"}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_elastic_stemmer_on_english_text:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_elastic_stemmer_on_estonian_text(self):
        url = reverse(f"{VERSION_NAMESPACE}:snowball")
        payload = {"text": "Seda teksti on kirjutatud puhtas eesti keeles!", "language": "estonian"}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_elastic_stemmer_on_estonian_text:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_elastic_stemmer_with_bogus_language_insert(self):
        url = reverse(f"{VERSION_NAMESPACE}:snowball")
        payload = {"text": "This is some text without any language specified!", "language": "non-existing-language"}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_elastic_stemmer_with_bogus_language_insert:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_elastic_stemmer_where_input_and_language_do_not_match(self):
        url = reverse(f"{VERSION_NAMESPACE}:snowball")
        payload = {"text": "This text is written in english but the language for stemmer that is used is estönian! Ümlauts are great!", "language": "estonian"}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_elastic_stemmer_on_estonian_text:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


@override_settings(CELERY_ALWAYS_EAGER=True)
class ApplyAnalyzersTests(APITransactionTestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.normal_user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("applyAnalyzers", self.test_index_name, self.normal_user)
        self.project.users.add(self.normal_user)

        self.admin_user = create_test_user('admin', 'my@email.com', 'pw')
        self.project.users.add(self.admin_user)

        self.unauthorized_user = create_test_user('unauthorized', 'my@email.com', 'pw')

        self.list_url = reverse(f"{VERSION_NAMESPACE}:apply_analyzers-list", kwargs={"project_pk": self.project.pk})
        self.client.login(username='user', password='pw')


    def tearDown(self) -> None:
        ec = ElasticCore()
        ec.delete_index(self.test_index_name)


    def test_unauthorized_endpoint_access(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        print_output("test_unauthorized_endpoint_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_unauthorized_project_access(self):
        self.client.login(username="unauthorized", password="pw")
        response = self.client.get(self.list_url)
        print_output("test_unauthorized_project_access:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_normal_process_application(self):
        payload = {
            "description": "hello there, kenobi.",
            "analyzers": ["stemmer"],
            "fields": [TEST_FIELD],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_normal_process_application:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        s = ElasticSearcher(indices=[self.test_index_name])
        for hit in s:
            new_field = f'{TEST_FIELD}_es.stems'
            self.assertTrue(new_field in hit)
            self.assertTrue(hit[new_field] != hit[TEST_FIELD])
            break


    def test_non_existing_fields_input(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": ["non_existing_field"],
            "analyzers": ["stemmer"],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_non_existing_fields_input:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_nested_field_process(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_NESTED_FIELDS],
            "analyzers": ["stemmer"],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_nested_field_process:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_blank_fields_input(self):
        payload = {
            "description": "random text",
            "fields": [],
            "analyzers": ["stemmer"],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_blank_fields_input:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_blank_indices_input(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["stemmer"],
            "stemmer_lang": "estonian",
            "indices": [],
            "query": json.dumps(TEST_QUERY, ensure_ascii=False)
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_blank_indices_input:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_non_existant_snowball_lang(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "stemmer_lang": "gibberish",
            "analyzers": ["stemmer"],
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_non_existant_snowball_lang:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_automatic_lang_detection_process(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["stemmer", "tokenizer"],
            "detect_lang": True,
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_automatic_lang_detection_process:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        s = ElasticSearcher(indices=[self.test_index_name])
        for hit in s:
            fields = [f'{TEST_FIELD}_es.tokenized_text', f'{TEST_FIELD}_es.stems']
            self.assertTrue(all([field in hit for field in fields]))
            self.assertTrue(all(hit[field] != hit[TEST_FIELD] for field in fields))
            break


    def test_exclusivity_for_detection_options_check(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["stemmer"],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}],
            "detect_lang": True
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_exclusivity_for_detection_options_check:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_normal_process_with_multiple_fields(self):
        payload = {
            "fields": [TEST_NESTED_FIELDS, TEST_FIELD],
            "detect_lang": True,
            "analyzers": ["stemmer"],
            "description": "suvakas bby",
            "query": json.dumps(TEST_QUERY, ensure_ascii=False)
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_normal_process_with_multiple_fields:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_processing_with_query(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["tokenizer"],
            "indices": [{"name": self.test_index_name}],
            "query": json.dumps(TEST_QUERY, ensure_ascii=False)
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_processing_with_query:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_check_for_either_detect_lang_or_snowball_lang_existence(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["stemmer"],
            "indices": [{"name": self.test_index_name}],
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_check_for_either_detect_lang_or_snowball_lang_existence:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_processing_with_just_tokenizer(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["tokenizer"],
            "indices": [{"name": self.test_index_name}],
            "query": json.dumps(TEST_QUERY, ensure_ascii=False)
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_processing_with_just_tokenizer:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        s = ElasticSearcher(indices=[self.test_index_name], query=TEST_QUERY)
        for hit in s:
            new_field = f'{TEST_FIELD}_es.tokenized_text'
            self.assertTrue(new_field in hit)
            self.assertTrue(hit[new_field] != hit[TEST_FIELD])


    def test_processing_with_non_standard_tokenizer(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "analyzers": ["tokenizer", "stemmer"],
            "detect_lang": True,
            "indices": [{"name": self.test_index_name}],
            "tokenizer": "whitespace"
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        print_output("test_processing_with_non_standard_tokenizer:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
