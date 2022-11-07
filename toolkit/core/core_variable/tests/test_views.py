from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.core_variable.models import CoreVariable
from toolkit.helper_functions import set_core_setting, get_core_setting
from toolkit.settings import CORE_SETTINGS
from toolkit.test_settings import TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output


class TestCoreVariableViews(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.admin_user = create_test_user("admin", "my@email.com", "pw", superuser=True)
        cls.non_admin_user = create_test_user("tester", "my@email.com", "pw")
        cls.url = f"{TEST_VERSION_PREFIX}/core_variables/"
        cls.health_url = f"{TEST_VERSION_PREFIX}/health/"

    def setUp(self):
        self.client.login(username="admin", password="pw")
        self.encrypted_field = "TEXTA_S3_SECRET_KEY"
        self.encrypted_value = "123456"

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

    def test_es_prefix_post(self):
        # update TEXTA_ES_URL to *
        payload = {"name": "TEXTA_ES_PREFIX", "value": "*"}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_incorrect_value:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # update TEXTA_ES_URL to normal value
        payload = {"name": "TEXTA_ES_PREFIX", "value": "texta"}
        response = self.client.post(self.url, payload)
        print_output('core_variable_post_es_prefix:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('name' in response.data)
        self.assertTrue('value' in response.data)
        self.assertTrue('env_value' in response.data)
        self.assertTrue('url' in response.data)
        variable_url = response.data['url']
        # delete
        response = self.client.delete(variable_url)
        print_output('core_variable_delete_es_prefix:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def _set_encrypted_field(self):
        set_core_setting(setting_name=self.encrypted_field, setting_value=self.encrypted_value)

    def test_that_secret_keys_are_automatically_encrypted_in_list_view(self):
        self._set_encrypted_field()
        response = self.client.get(self.url)
        print_output("test_that_secret_keys_are_automatically_encrypted_in_list_view:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        field_dict = [item for item in response.data if item["name"] == self.encrypted_field][0]
        # Since token is in the Base64 format you can check for the success by looking for two equal signs.
        self.assertTrue("==" in field_dict["value"])

    def test_that_set_core_settings_encrypts_secret_settings(self):
        self._set_encrypted_field()
        setting = CoreVariable.objects.get(name=self.encrypted_field)
        print_output("test_that_set_core_settings_encrypts_secret_settings:corevariable value", setting.value)
        self.assertTrue("==" in setting.value)

    def test_that_get_core_settings_decrypts_secret_settings(self):
        self._set_encrypted_field()
        value = get_core_setting(self.encrypted_field)
        print_output("test_that_get_core_settings_decrypts_secret_settings:value", value)
        self.assertEqual(value, self.encrypted_value)

    def test_that_detail_view_is_encrypted(self):
        self._set_encrypted_field()
        cv = CoreVariable.objects.get(name=self.encrypted_field)
        url = reverse("v2:corevariable-detail", kwargs={"pk": cv.pk})
        response = self.client.get(url)
        print_output("test_that_detail_view_is_encrypted:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue("==" in response.data["value"])

    def test_that_changing_a_setting_inside_view_encrypts_it(self):
        self._set_encrypted_field()
        cv = CoreVariable.objects.get(name=self.encrypted_field)
        url = reverse("v2:corevariable-detail", kwargs={"pk": cv.pk})
        new_password = "bourgeoisie"
        response = self.client.put(url, data={"name": self.encrypted_field, "value": new_password}, format="json")
        print_output("test_that_changing_a_setting_inside_view_encrypts_it:response.data", response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        value = get_core_setting(self.encrypted_field)
        self.assertEqual(value, new_password)
