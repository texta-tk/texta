from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.test_settings import TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output


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


    # TODO Figure out a way to properly overwrite core variables for testing purposes.
    def test_health_without_proper_elasticsearch_connection(self):
        pass
