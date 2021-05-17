import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from toolkit.elastic.tools.document import ElasticDocument
from toolkit.tools.utils_for_tests import create_test_user, project_creation, print_output


class SearchFieldsTaggerIndexViewTests(APITestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("SearchFieldsTaggerTestProject", "test_search_fields_tagger_index", self.user)
        self.project.users.add(self.user)
        self.url = reverse("v1:search_fields_tagger-list", kwargs={"project_pk": self.project.pk})

        self.uuid = "adasda-5874856a-das4das98f6"
        self.document = {
            "Field_1": "This is sentence1. This is sentence2. This is sentence3. This is sentence4. This is sentence5.",
            "Field_2": "This is a different sentence.",
            "Field_3": "This is test data.",
            "uuid": self.uuid}

        self.ed = ElasticDocument(index="test_search_fields_tagger_index")

        self.ed.add(self.document)
        self.client.login(username='user', password='pw')

    def tearDown(self) -> None:
        from toolkit.elastic.tools.core import ElasticCore
        ElasticCore().delete_index(index="test_search_fields_tagger_index", ignore=[400, 404])

    def test_search_fields_tagger(self):
        payload = {
                    "indices": [{"name": "test_search_fields_tagger_index"}],
                    "description": "test",
                    "query": json.dumps({}),
                    "fields": ["Field_1"],
                    "fact_name": "test_name"
                }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_fields_tagger:url', self.url)
        print_output('test_search_fields_tagger:response', response)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_search_fields_tagger_index(self):
        payload = {
                    "indices": [{"name": "test_search_fields_tagger_index_none"}],
                    "description": "test",
                    "query": json.dumps({}),
                    "fields": ["Field_1"],
                    "fact_name": "test_name"
                }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_fields_tagger_index:url', self.url)
        print_output('test_search_fields_tagger_index:response', response)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_fields_tagger_fields(self):
        payload = {
                    "indices": [{"name": "test_search_fields_tagger_index"}],
                    "description": "test",
                    "query": json.dumps({}),
                    "fields": ["Field_4"],
                    "fact_name": "test_name"
                }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_fields_tagger_fields:url', self.url)
        print_output('test_search_fields_tagger_fields:response', response)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class SearchQueryTaggerIndexViewTests(APITestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("SearchQueryTaggerTestProject", "test_search_query_tagger_index", self.user)
        self.project.users.add(self.user)
        self.url = reverse("v1:search_query_tagger-list", kwargs={"project_pk": self.project.pk})

        self.uuid = "adasda-5874856a-das4das98f5"
        self.document = {
            "Field_1": "This is sentence1. This is sentence2. This is sentence3. This is sentence4. This is sentence5.",
            "Field_2": "This is a different sentence.",
            "Field_3": "This is test data.",
            "uuid": self.uuid}

        self.ed = ElasticDocument(index="test_search_query_tagger_index")

        self.ed.add(self.document)
        self.client.login(username='user', password='pw')

    def tearDown(self) -> None:
        from toolkit.elastic.tools.core import ElasticCore
        ElasticCore().delete_index(index="test_search_query_tagger_index", ignore=[400, 404])

    def test_search_query_tagger(self):
        payload = {
                    "indices": [{
                        "name": "test_search_query_tagger_index"
                    }],
                    "description": "test",
                    "query": json.dumps({
                        "query": {
                            "match": {
                                "Field_3": {
                                    "query": "This is test data."
                                }
                            }
                        }
                    }),
                    "fields": ["Field_2"],
                    "fact_name": "test_name",
                    "fact_value": "test_value"
                }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_query_tagger:url', self.url)
        print_output('test_search_query_tagger:response', response)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_search_query_tagger_index(self):
        payload = {
                    "indices": [{
                        "name": "test_search_query_tagger_index_none"
                    }],
                    "description": "test",
                    "query": json.dumps({
                        "query": {
                            "match": {
                                "Field_3": {
                                    "query": "This is test data."
                                }
                            }
                        }
                    }),
                    "fields": ["Field_1"],
                    "fact_name": "test_name",
                    "fact_value": "test_value"
                }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_query_tagger_index:url', self.url)
        print_output('test_search_query_tagger_index:response', response)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_query_tagger_fields(self):
        payload = {
                    "indices": [{
                        "name": "test_search_query_tagger_index"
                    }],
                    "description": "test",
                    "query": json.dumps({
                        "query": {
                            "match": {
                                "Field_3": {
                                    "query": "This is test data."
                                }
                            }
                        }
                    }),
                    "fields": ["Field_4"],
                    "fact_name": "test_name",
                    "fact_value": "test_value"
                }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_query_tagger_fields:url', self.url)
        print_output('test_search_query_tagger_fields:response', response)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
