from django.test import TestCase
from rest_framework import status

from toolkit.test_settings import TEST_VERSION_PREFIX
from toolkit.settings import CORE_SETTINGS
from toolkit.tools.utils_for_tests import create_test_user, print_output


class TestCoreVariableViews(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.admin_user = create_test_user("admin", "my@email.com", "pw", superuser=True)
        cls.non_admin_user = create_test_user("tester", "my@email.com", "pw")
        cls.url = f"{TEST_VERSION_PREFIX}/core_variables/"
        cls.health_url = f"{TEST_VERSION_PREFIX}/health/"


    def setUp(self):
        self.client.login(username="admin", password="pw")


    def test_es_url_post(self):
        # update TEXTA_ES_URL to something incorrect
        payload = {"name": "TEXTA_ES_URL", "value": "somerandomstring"}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_incorrect_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # update TEXTA_ES_URL to normal value
        payload = {"name": "TEXTA_ES_URL", "value": CORE_SETTINGS["TEXTA_ES_URL"]}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('name' in response.data)
        self.assertTrue('value' in response.data)
        self.assertTrue('env_value' in response.data)
        self.assertTrue('url' in response.data)
        es_variable_url = response.data['url']
        # let's now check health
        response = self.client.get(self.health_url)
        self.assertEqual(response.data['services']['elastic']['alive'], True)
        # delete
        response = self.client.delete(es_variable_url)
        print_output('core_variable_delete_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


    def test_mlp_url_post(self):
        # update TEXTA_MLP_URL to something incorrect
        payload = {"name": "TEXTA_MLP_URL", "value": "somerandomstring"}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_incorrect_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # update TEXTA_MLP_URL to something incorrect with protocol
        payload = {"name": "TEXTA_MLP_URL", "value": "ftp://somerandomstring"}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_incorrect_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # update TEXTA_MLP_URL to normal value
        payload = {"name": "TEXTA_MLP_URL", "value": CORE_SETTINGS["TEXTA_MLP_URL"]}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('name' in response.data)
        self.assertTrue('value' in response.data)
        self.assertTrue('env_value' in response.data)
        self.assertTrue('url' in response.data)
        mlp_variable_url = response.data['url']
        # let's now check health
        response = self.client.get(self.health_url)
        self.assertEqual(response.data['services']['elastic']['alive'], True)   
        # delete
        response = self.client.delete(mlp_variable_url)
        print_output('core_variable_delete_es_url:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


    def test_non_admin_forbidden(self):
        # login as non-admin user
        self.client.login(username="tester", password="pw")
        # try get
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # try post
        payload = {"name": "TEXTA_ES_URL", "value": "somerandomstring"}
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # go back to being admin
        self.client.login(username="admin", password="pw")
