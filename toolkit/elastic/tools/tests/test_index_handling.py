import elasticsearch_dsl
import requests
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.elastic.index.models import Index
from texta_elastic.core import ElasticCore
from toolkit.settings import CORE_SETTINGS
from toolkit.test_settings import TEST_INDEX, VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, project_creation


ES_URL = CORE_SETTINGS["TEXTA_ES_URL"]


class ElasticIndexViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        """ user needs to be admin, because of changed indices permissions """
        cls.default_password = 'pw'
        cls.default_username = 'indexOwner'
        cls.user = create_test_user(cls.default_username, 'my@email.com', cls.default_password)
        # create admin to test indices removal from project
        cls.admin = create_test_user(name='admin', password="1234")
        cls.admin.is_superuser = True
        cls.admin.save()
        cls.project = project_creation("ElasticTestProject", TEST_INDEX, cls.user)
        cls.project.users.add(cls.user)


    def __create_locked_index(self, index_name: str):
        index_url = f"{ES_URL}/{index_name}"
        create_index = requests.put(index_url)
        lock_index = requests.put(f"{index_url}/_settings", json={
            "index": {
                "blocks": {
                    "read_only_allow_delete": True
                }
            }
        })


    def setUp(self):
        self.client.login(username=self.admin, password="1234")
        self.index_url = reverse(f"{VERSION_NAMESPACE}:index-list")


    def tearDown(self):
        index_names = ["first_index_duplicate", "same_name_index", "test_closed_sync", "open_index_creation", "closed_index_creation", "open_index_2", "closed_index_2", "bofuun", "my_new_index"]
        for index in index_names:
            requests.delete(f"{ES_URL}/{index}")


    def test_open_index_creation(self):
        response = self.client.post(self.index_url, format="json", data={
            "name": "open_index_creation",
            "is_open": True
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        es_response = requests.head(f"{ES_URL}/open_index_creation")
        self.assertTrue(es_response.status_code == status.HTTP_200_OK)
        is_open_response = requests.get(f"{ES_URL}/_cat/indices/open_index_creation?h=status&format=json").json()[0]
        self.assertTrue(is_open_response["status"] == "open")


    def test_closed_index_creation(self):
        response = self.client.post(self.index_url, format="json", data={
            "name": "closed_index_creation",
            "is_open": False
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        es_response = requests.head(f"{ES_URL}/closed_index_creation")
        self.assertTrue(es_response.status_code == status.HTTP_200_OK)
        is_closed_response = requests.get(f"{ES_URL}/_cat/indices/closed_index_creation?h=status&format=json").json()[0]
        self.assertTrue(is_closed_response["status"] == "close")


    def test_closing_index(self):
        # Create open index
        response = self.client.post(self.index_url, format="json", data={
            "name": "open_index_2",
            "is_open": True
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        pk = Index.objects.last().pk
        url = f"{self.index_url}{pk}/close_index/"
        closing_response = self.client.patch(url)
        self.assertTrue(closing_response.status_code == status.HTTP_200_OK)
        is_closed_response = requests.get(f"{ES_URL}/_cat/indices/open_index_2?h=status&format=json").json()[0]
        self.assertTrue(is_closed_response["status"] == "close")


    def test_opening_index(self):
        # Create open index
        response = self.client.post(self.index_url, format="json", data={
            "name": "closed_index_2",
            "is_open": False
        })
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        pk = Index.objects.last().pk
        url = f"{self.index_url}{pk}/open_index/"
        opening_response = self.client.patch(url)
        self.assertTrue(opening_response.status_code == status.HTTP_200_OK)
        is_open_response = requests.get(f"{ES_URL}/_cat/indices/closed_index_2?h=status&format=json").json()[0]
        self.assertTrue(is_open_response["status"] == "open")


    def test_no_wildcards_in_index_for_security(self):
        response = self.client.post(self.index_url, format="json", data={
            "name": "*a*",
            "is_open": True
        })
        self.assertTrue(response.status_code == status.HTTP_400_BAD_REQUEST)


    def test_that_only_superusers_can_access_index_endpoints(self):
        self.client.login(username=self.default_username, password=self.default_password)
        response = self.client.get(self.index_url)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        pk = Index.objects.create(name="bofuun")
        item_response = self.client.get(f"{self.index_url}{pk}/")
        self.assertTrue(item_response.status_code == status.HTTP_403_FORBIDDEN)


    def test_index_synchronisation(self):
        # Delete all indices for security sake.
        Index.objects.all().delete()
        opened, closed = ElasticCore().get_indices()
        elastic_content = set(opened + closed)
        response = self.client.post(f"{self.index_url}sync_indices/")
        self.assertTrue(response.status_code == status.HTTP_204_NO_CONTENT)
        toolkit_content = set([index.name for index in Index.objects.all()])

        # Check whether all elasticsearch indices are present in tk
        # and vice-versa.
        self.assertTrue(len(elastic_content - toolkit_content) == 0)
        self.assertTrue(len(toolkit_content - elastic_content) == 0)


    def test_proper_open_closed_test_transferal_after_sync(self):
        Index.objects.all().delete()

        created_response = requests.put(f"{ES_URL}/test_closed_sync")  # Add the index into Elasticsearch.
        closed_response = requests.post(f"{ES_URL}/test_closed_sync/_close")  # Close said index.
        response = self.client.post(f"{self.index_url}sync_indices/")  # Do the deed.

        closed_index = Index.objects.get(name="test_closed_sync", is_open=False)
        self.assertTrue(closed_index is not None)


    def test_creating_an_index_with_the_same_name(self):
        created_response = requests.put(f"{ES_URL}/same_name_index")
        response = self.client.post(self.index_url, format="json", data={
            "name": "same_name_index",
            "is_open": False
        })
        closed_index = Index.objects.get(name="same_name_index", is_open=False)


    def test_project_creation_using_locked_indices(self):
        """
        There was a bug case that warrants this test case.
        In case any of the indices in Elasticsearch are locked for whatever reason,
        then project creation fails because it contains/contained  lazy index creation
        which ignores existing indices and thus created FORBIDDEN_ACCESS errors in Elasticsearch.
        """
        index_names = ["locked_index_{}".format(i) for i in range(1, 5)]
        for index in index_names:
            self.__create_locked_index(index)

        response = self.client.post(reverse(f"{VERSION_NAMESPACE}:project-list"), format="json", data={
            "title": "faulty_project",
            "indices_write": index_names,
            "users_write": [self.admin.username]
        })

        ec = ElasticCore()
        for index in index_names:
            ec.delete_index(index)

        self.assertTrue(response.status_code == status.HTTP_201_CREATED)


    def test_creating_closed_and_open_index_with_duplicate_names(self):
        """
        Created because of an old bug where trying to create an closed index with
        the same name as existing opened one caused the whole endpoint to die.
        """

        first_index = self.client.post(self.index_url, format="json", data={
            "name": "first_index_duplicate",
            "is_open": False
        })
        self.assertTrue(first_index.status_code == status.HTTP_201_CREATED)

        second_index = self.client.post(self.index_url, format="json", data={
            "name": "first_index_duplicate",
            "is_open": False
        })

        self.assertTrue(second_index.status_code == status.HTTP_400_BAD_REQUEST)
        list_view = self.client.get(self.index_url)
        self.assertTrue(list_view.status_code == status.HTTP_200_OK)

    def test_update_existing_index(self):
        """
        Create an index and update it.
        """

        new_index = self.client.post(self.index_url, format="json", data={
            "name": "my_new_index",
            "is_open": False
        })
        self.assertTrue(new_index.status_code == status.HTTP_201_CREATED)

        pk = Index.objects.last().pk
        url = f"{self.index_url}{pk}/"
        new_index_update = self.client.patch(url, format="json", data={
            "description": "testing",
            "added_by": "tester",
            "test": True,
            "source": "test",
            "client": "texta",
            "domain": "emails"
        })
        self.assertTrue(new_index_update.status_code == status.HTTP_201_CREATED)

    def test_update_existing_index(self):
        """
        Create an index and update it.
        """

        new_index = self.client.post(self.index_url, format="json", data={
            "name": "my_new_index",
            "is_open": False
        })
        self.assertTrue(new_index.status_code == status.HTTP_201_CREATED)

        pk = Index.objects.last().pk
        url = f"{self.index_url}{pk}/"
        new_index_update = self.client.patch(url, format="json", data={
            "description": "testing",
            "added_by": "tester",
            "test": True,
            "source": "test",
            "client": "texta",
            "domain": "emails"
        })
        self.assertTrue(new_index_update.status_code == status.HTTP_201_CREATED)


    def test_that_index_count_matches_reality(self):
        ec = ElasticCore()
        list_url = reverse(f"{VERSION_NAMESPACE}:index-list")
        response = self.client.get(list_url)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        test_index = [index for index in response.data if index["name"] == TEST_INDEX][0]

        counter = 0
        # Use params to fetch 5k documents with first request.
        s = elasticsearch_dsl.Search(using=ec.es, index=TEST_INDEX).params(size=5000)
        for hit in s.scan():
            counter += 1

        self.assertTrue(counter == test_index["doc_count"])
