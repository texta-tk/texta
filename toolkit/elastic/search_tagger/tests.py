import json
import uuid

from django.test import override_settings
from django.urls import reverse
from elasticsearch_dsl import Search
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.document import ElasticDocument

from toolkit.test_settings import VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class SearchFieldsTaggerIndexViewTests(APITestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.index_uuid = uuid.uuid4().hex[:5]
        self.new_test_index_name = f"ttk_test_fields_tagger_{self.index_uuid}"

        self.ed = ElasticDocument(index=self.new_test_index_name)
        self.ed.core.es.indices.create(index=self.new_test_index_name, ignore=[400, 404])

        self.project = project_creation("SearchFieldsTaggerTestProject", self.new_test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = reverse(f"{VERSION_NAMESPACE}:search_fields_tagger-list", kwargs={"project_pk": self.project.pk})

        self.uuid = uuid.uuid4().hex[:10]
        self.document = {
            "Field_1": "This is sentence1. This is sentence2. This is sentence3. This is sentence4. This is sentence5.",
            "Field_2": "This is a different sentence.",
            "Field_3": "This is test data.",
            "newline_break": "olgu\nõnnistatud\npüha\nkäsikranaat",
            "array_break": ["olgu", "õnnistatud", "püha", "käsikranaat"],
            "uuid": self.uuid
        }

        self.ed.add(self.document)
        self.client.login(username='user', password='pw')

    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index=self.new_test_index_name, ignore=[400, 404])

    def test_search_fields_tagger(self):
        fact_name = f"test_name_{uuid.uuid4().hex}"
        payload = {
            "indices": [{"name": self.new_test_index_name}],
            "description": "test",
            "fields": ["Field_1"],
            "fact_name": fact_name
        }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_fields_tagger:url', self.url)
        print_output('test_search_fields_tagger:response', response)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ea = ElasticAggregator()
        facts = ea.facts(size=100, filter_by_fact_name=fact_name)
        self.assertNotEqual(len(facts), 0)

    def test_new_line_break_into_facts(self):
        payload = {
            "indices": [{"name": self.new_test_index_name}],
            "description": "test",
            "fields": ["newline_break"],
            "use_breakup": True,
            "breakup_character": "\n",
            "fact_name": "test_name"
        }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_new_line_break_into_facts:url', self.url)
        print_output('test_new_line_break_into_facts:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        s = Search(using=self.ed.core.es, index=self.new_test_index_name)
        s = s.query("match", uuid=self.uuid)
        for doc in s.execute():
            dict_doc = doc.to_dict()
            facts = dict_doc.get("texta_facts", [])
            print_output('test_new_line_break_into_facts:facts', facts)
            self.assertTrue(len(facts) == 4)

    def test_array_break_into_facts(self):
        payload = {
            "indices": [{"name": self.new_test_index_name}],
            "description": "test",
            "fields": ["array_break"],
            "use_breakup": True,
            "breakup_character": "\n",
            "fact_name": "test_name"
        }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_array_break_into_facts:url', self.url)
        print_output('test_array_break_into_facts:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        s = Search(using=self.ed.core.es, index=self.new_test_index_name)
        s = s.query("match", uuid=self.uuid)
        for doc in s.execute():
            dict_doc = doc.to_dict()
            facts = dict_doc.get("texta_facts", [])
            print_output('test_array_break_into_facts:facts', facts)
            self.assertTrue(len(facts) == 4)

    def test_search_fields_tagger_index(self):
        payload = {
            "indices": [{"name": "index_that_doesn't_exist"}],
            "description": "test",
            "fields": ["Field_1"],
            "fact_name": "test_name"
        }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_fields_tagger_index:url', self.url)
        print_output('test_search_fields_tagger_index:response', response)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_fields_tagger_fields(self):
        payload = {
            "indices": [{"name": self.new_test_index_name}],
            "description": "test",
            "fields": ["Field_4"],
            "fact_name": "test_name"
        }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_fields_tagger_fields:url', self.url)
        print_output('test_search_fields_tagger_fields:response.data', response.data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(CELERY_ALWAYS_EAGER=True)
class SearchQueryTaggerIndexViewTests(APITransactionTestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.new_test_index_name = f"ttk_test_query_tagger_{uuid.uuid4().hex[:5]}"
        self.project = project_creation("SearchQueryTaggerTestProject", self.new_test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = reverse("v2:search_query_tagger-list", kwargs={"project_pk": self.project.pk})

        self.uuid = "adasda-5874856a-das4das98f5"
        self.document = {
            "Field_1": "This is sentence1. This is sentence2. This is sentence3. This is sentence4. This is sentence5.",
            "Field_2": "This is a different sentence.",
            "Field_3": "This is test data.",
            "uuid": self.uuid
        }

        self.ed = ElasticDocument(index=self.new_test_index_name)

        self.ed.add(self.document)
        self.client.login(username='user', password='pw')

    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index=self.new_test_index_name, ignore=[400, 404])

    def test_search_query_tagger(self):
        fact_name = f"test_name_{uuid.uuid4().hex}"
        payload = {
            "indices": [{
                "name": self.new_test_index_name
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
            "fact_name": fact_name,
            "fact_value": "test_value"
        }

        response = self.client.post(self.url, payload, format="json")
        print_output('test_search_query_tagger:url', self.url)
        print_output('test_search_query_tagger:response', response)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ea = ElasticAggregator()
        facts = ea.facts(size=100, filter_by_fact_name=fact_name)
        self.assertNotEqual(len(facts), 0)

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
                "name": self.new_test_index_name
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
