import inspect

# Create your tests here.
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.test_settings import TEST_INDEX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class TestCeleryAccess(APITestCase):


    def setUp(self):
        self.normal_user = create_test_user('normal_user', 'my@email.com', 'pw')
        self.admin_user = create_test_user('admin_user', 'my@email.com', 'pw', superuser=True)
        self.project = project_creation("AnonymizerTestProject", TEST_INDEX, self.normal_user)
        self.project.users.add(self.normal_user, self.admin_user)

        self.client.login(username='normal_user', password='pw')


    def test_normal_user_access_to_stats_page(self):
        url = reverse("v2:queue_stats")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_normal_user_access_to_purge_page(self):
        url = reverse("v2:purge_tasks")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_normal_user_access_to_count_page(self):
        url = reverse("v2:count_tasks")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_admin_access_to_stats_page(self):
        self.client.login(username='admin_user', password='pw')
        url = reverse("v2:queue_stats")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        # We check for 404 because that's the status code returned when Celery isn't found which can be in the case of tests.
        self.assertTrue(response.status_code == status.HTTP_200_OK or response.status_code == status.HTTP_404_NOT_FOUND)


    def test_admin_access_to_count_page(self):
        self.client.login(username='admin_user', password='pw')
        url = reverse("v2:count_tasks")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_unauthenticated_access_to_count_page(self):
        self.client.logout()
        url = reverse("v2:count_tasks")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_unauthenticated_access_to_stats_page(self):
        url = reverse("v2:queue_stats")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_unauthenticated_access_to_purge_page(self):
        url = reverse("v2:purge_tasks")
        response = self.client.post(url)
        print_output(f"{inspect.currentframe().f_code.co_name}:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)
