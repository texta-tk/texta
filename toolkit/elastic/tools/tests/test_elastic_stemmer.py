from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.test_settings import TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output


@override_settings(CELERY_ALWAYS_EAGER=True)
class ElasticStemmerViewTests(APITransactionTestCase):

    def setUp(self):
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.client.login(username='taggerOwner', password='pw')
        self.url = f'{TEST_VERSION_PREFIX}/elastic/snowball/'


    def test_stem_english(self):
        payload = {
            "text": "Foxes",
            "language": "english",
        }
        response = self.client.post(self.url, payload)
        print_output('test_snowball_estonian:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assert response.data["text"].lower() == "fox"


    def test_incorrect_language(self):
        payload = {
            "text": "Autoriteetidega.",
            "language": "ajshdf",
        }
        response = self.client.post(self.url, payload)
        print_output('test_snowball_incorrect_language:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
