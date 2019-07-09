from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit import permissions as toolkit_permissions
from toolkit.test_settings import TEST_INDEX


class ProjectViewTests(APITestCase):

    def setUp(self):
        # Create a new User
        self.user = create_test_user(name='user', password='pw')
        self.project = Project.objects.create(title='testproj', owner=self.user, indices=[TEST_INDEX])
        self.client = APIClient()
        self.client.login(username='user', password='pw')

    def test_get_fields(self):
        url = f'/projects/{self.project.id}/get_fields/'
        response = self.client.get(url)
        print_output('get_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, list))
        self.assertTrue(TEST_INDEX in [field['index'] for field in response.data])
