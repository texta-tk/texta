import json

from django.urls import reverse
from rest_framework.test import APITestCase
from toolkit.tools.utils_for_tests import create_test_user, project_creation, print_output
from texta_elastic.document import ElasticDocument
from rest_framework import status


class SummarizerIndexViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user('user', 'my@email.com', 'pw')
        cls.project = project_creation("SummarizerTestProject", "test_summarizer_index", cls.user)
        cls.project.users.add(cls.user)
        cls.url = reverse("v2:summarizer_index-list", kwargs={"project_pk": cls.project.pk})

        cls.uuid = "adasda-5874856a-das4das98f4"
        cls.document = {"Field_1": "This is sentence1. This is sentence2. This is sentence3. This is sentence4. This is sentence5.", "uuid": cls.uuid}

        cls.ed = ElasticDocument(index="test_summarizer_index")

        cls.ed.add(cls.document)

        cls.summarizer_id = None

    def setUp(self):
        self.client.login(username='user', password='pw')

    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index="test_summarizer_index", ignore=[400, 404])

    def test(self):
        self.run_test_summarizer_create()

    def run_test_summarizer_create(self):
        payload = {
            "description": "TestSummarizer",
            "query": json.dumps({"query": {"match_all": {}}}, ensure_ascii=False),
            "fields": ["Field_1"]
        }

        response = self.client.post(self.url, payload)
        print_output('test_summarizer_create:response', response)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
