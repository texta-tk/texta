from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.user_profile.models import UserProfile
from toolkit.tools.utils_for_tests import create_test_user, print_output

class UserProfileSignalsAndViewsTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('user', 'my@email.com', 'pw')


    def setUp(self):
        self.client.login(username='user', password='pw')


    def test_health(self):
        '''Tests if health endpoint responding with decent values.'''
        response = self.client.get('/health')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print_output('test_health:response.data', response.data)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('memory' in response.data)
        self.assertTrue('disk' in response.data)
        self.assertTrue('cpu' in response.data)
        self.assertTrue('elastic_alive' in response.data)
        self.assertTrue('version' in response.data)