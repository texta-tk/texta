from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.test_settings import TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output

import torch

class HealthViewsTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user('user', 'my@email.com', 'pw')


    def setUp(self):
        self.client.login(username='user', password='pw')


    def test_health(self):
        '''Tests if health endpoint responding with decent values.'''
        response = self.client.get(f'{TEST_VERSION_PREFIX}/health')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print_output('test_health:response.data', response.data)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('host' in response.data)
        self.assertTrue('services' in response.data)
        self.assertTrue('toolkit' in response.data)

        # Check if all counted devices are present in devices list
        self.assertTrue(len(response.data['host']['gpu']['devices']) == response.data['host']['gpu']['count'])

        if torch.cuda.is_available():
            # Check if all required fields for device 0 are present if GPU is available
            device_0 = response.data['host']['gpu']['devices'][0]
            self.assertTrue("id" in device_0)
            self.assertTrue("name" in device_0)
            self.assertTrue("memory" in device_0)
            self.assertTrue("free" in device_0["memory"])
            self.assertTrue("used" in device_0["memory"])
            self.assertTrue("total" in device_0["memory"])
            self.assertTrue("unit" in device_0["memory"])



    # TODO Figure out a way to properly overwrite core variables for testing purposes.
    def test_health_without_proper_elasticsearch_connection(self):
        pass
