from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from toolkit.elastic.tools.core import ElasticCore
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_NESTED_FIELDS, VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class SnowballElasticStemmerViewTest(APITestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("elasticSnowballStemmer", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='user', password='pw')


    def test_elastic_stemmer_without_language_specified(self):
        url = reverse(f"{VERSION_NAMESPACE}:snowball")
        payload = {"text": "This is some text without any language specified!"}
        response = self.client.post(url, data=payload, format="json")
        print_output("test_elastic_stemmer_without_language_specified:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


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
class ApplySnowballStemmerTests(APITransactionTestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.normal_user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("applyStemmer", self.test_index_name, self.normal_user)
        self.project.users.add(self.normal_user)

        self.admin_user = create_test_user('admin', 'my@email.com', 'pw')
        self.project.users.add(self.admin_user)

        self.unauthorized_user = create_test_user('unauthorized', 'my@email.com', 'pw')

        self.list_url = reverse("v2:apply_snowball-list", kwargs={"project_pk": self.project.pk})
        self.client.login(username='user', password='pw')


    def tearDown(self) -> None:
        ec = ElasticCore()
        ec.delete_index(self.test_index_name)


    def test_unauthorized_endpoint_access(self):
        self.client.logout()
        response = self.client.get(self.list_url)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        print_output("test_unauthorized_endpoint_access:response.data", response.data)


    def test_unauthorized_project_access(self):
        self.client.login(username="unauthorized", password="pw")
        response = self.client.get(self.list_url)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        print_output("test_unauthorized_project_access:response.data", response.data)


    def test_normal_process_application(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_normal_process_application:response.data", response.data)


    def test_non_existing_fields_input(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": ["non_existing_field"],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        print_output("test_non_existing_fields_input:response.data", response.data)


    def test_nested_field_process(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_NESTED_FIELDS],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_nested_field_process:response.data", response.data)


    def test_blank_fields_input(self):
        payload = {
            "description": "random text",
            "fields": [],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        print_output("test_blank_fields_input:response.data", response.data)


    def test_blank_indices_input(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "stemmer_lang": "estonian",
            "indices": []
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_blank_indices_input:response.data", response.data)


    def test_non_existant_snowball_lang(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "stemmer_lang": "gibberish",
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        print_output("test_non_existant_snowball_lang:response.data", response.data)


    def test_automatic_lang_detection_process(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "detect_lang": True,
            "indices": [{"name": self.test_index_name}]
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_automatic_lang_detection_process:response.data", response.data)


    def test_exclusivity_for_detection_options_check(self):
        payload = {
            "description": "hello there, kenobi.",
            "fields": [TEST_FIELD],
            "stemmer_lang": "estonian",
            "indices": [{"name": self.test_index_name}],
            "detect_lang": True
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        print_output("test_exclusivity_for_detection_options_check:response.data", response.data)


    def test_normal_process_with_multiple_fields(self):
        payload = {
            "indices": [{"name": "texta_test_index"}],
            "fields": [TEST_NESTED_FIELDS, TEST_FIELD],
            "detect_lang": True,
            "description": "suvakas bby"
        }
        response = self.client.post(self.list_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)
        print_output("test_normal_process_with_multiple_fields:response.data", response.data)
