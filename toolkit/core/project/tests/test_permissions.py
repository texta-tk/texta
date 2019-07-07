from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import create_test_user
from toolkit import permissions as toolkit_permissions


class ProjectPermissionsTests(APITestCase):

    def setUp(self):
        # Create a new User
        self.user_1 = create_test_user(name='user_1', password='pw')
        self.user_2 = create_test_user(name='user_2', password='pw')
        self.user_3 = create_test_user(name='user_3', password='pw')
        self.project = Project.objects.create(title='testproj', owner=self.user_1)
        self.project.users.add(self.user_2)
        self.project.users.add(self.user_1)
        print(self.project.users.all())
        self.client = APIClient()
        # Test on the core.taggers ModelViewSet url
        self.basic_test_url = f'/projects/{self.project.id}/lexicons/'

    def test_project_with_user_listed(self):
        '''Test if listed users allowed to see content'''
        self.client.login(username='user_1', password='pw')
        response = self.client.get(self.basic_test_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.login(username='user_2', password='pw')
        response = self.client.get(self.basic_test_url)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_project_with_user_not_listed(self):
        '''Test if unlisted users rejected'''
        self.client.login(username='user_3', password='pw')
        response = self.client.get(self.basic_test_url)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
