from django.urls import reverse
from rest_framework.test import APITestCase
from toolkit.tools.utils_for_tests import create_test_user, print_output
from rest_framework import status


class SummarizerSummarizeViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user('user', 'my@email.com', 'pw')
        cls.url = reverse("v2:summarizer_summarize")

        cls.summarizer_id = None

    def setUp(self):
        self.client.login(username='user', password='pw')

    def test(self):
        self.run_test_summarizer_summarize()

    def run_test_summarizer_summarize(self):
        payload = {
            "text": "This is sentence 1. This is sentence 2. This is sentence 3. This is sentence 4.",
        }

        response = self.client.post(self.url, payload)
        print_output('test_summarizer_summarize:response', response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
