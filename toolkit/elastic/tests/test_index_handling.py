import requests
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.models import Index
from toolkit.settings import ES_URL
from toolkit.test_settings import TEST_INDEX, TEST_VERSION_PREFIX
from toolkit.tools.common_utils import project_creation
from toolkit.tools.utils_for_tests import create_test_user


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
        cls.project = project_creation("ElasticTestProject", TEST_INDEX)
        cls.project.users.add(cls.user)


    def setUp(self):
        self.client.login(username=self.admin, password="1234")
        self.index_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/index/'


    def tearDown(self):
        index_names = ["same_name_index", "test_closed_sync", "open_index_creation", "closed_index_creation", "open_index_2", "closed_index_2", "bofuun"]
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
        opened, closed = ElasticCore().get_indices()

        created_response = requests.put(f"{ES_URL}/test_closed_sync")
        closed_response = requests.post(f"{ES_URL}/test_closed_sync/_close")
        response = self.client.post(f"{self.index_url}sync_indices/")

        closed_index = Index.objects.get(name="test_closed_sync", is_open=False)
        self.assertTrue(closed_index is not None)


    def test_creating_an_index_with_the_same_name(self):
        created_response = requests.put(f"{ES_URL}/same_name_index")
        response = self.client.post(self.index_url, format="json", data={
            "name": "same_name_index",
            "is_open": False
        })
        closed_index = Index.objects.get(name="same_name_index", is_open=False)