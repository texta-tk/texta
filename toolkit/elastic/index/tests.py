from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.elastic.index.models import Index
from texta_elastic.core import ElasticCore
from toolkit.tools.utils_for_tests import create_test_user, print_output


class IndexViewsTest(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('user', 'my@email.com', 'pw', superuser=True)

    def setUp(self) -> None:
        self.client.login(username="user", password="pw")
        self.ec = ElasticCore()
        self.ids = []
        self.index_names = [f"test_for_index_endpoint_with_ridiculously_large_name_{i}" for i in range(30)]

        for index_name in self.index_names:
            index, is_created = Index.objects.get_or_create(name=index_name)
            self.ec.es.indices.create(index=index_name, ignore=[400, 404])
            self.ids.append(index.pk)

    def test_bulk_delete(self):
        url = reverse("v2:index-bulk-delete")
        response = self.client.post(url, data={"ids": self.ids}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for index_name in self.index_names:
            self.assertFalse(self.ec.es.indices.exists(index_name))
        print_output("test_bulk_delete:response.data", response.data)

    def tearDown(self) -> None:
        indices = Index.objects.filter(pk__in=self.ids)
        names = [index.name for index in indices]
        if names:
            indices.delete()
            for index in names:
                self.ec.delete_index(index=index, ignore=[400, 404])

    def test_that_unlocking_indices_works(self):
        url = reverse("v2:index-clear-read-only-blocks")
        response = self.client.post(url)
        print_output("test_that_unlocking_indices_works:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
