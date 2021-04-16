from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.test_settings import (
    TEST_INDEX,
    VERSION_NAMESPACE
)
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
