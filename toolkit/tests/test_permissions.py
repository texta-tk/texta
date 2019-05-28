from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.utils.utils_for_tests import create_test_user
from toolkit import permissions as toolkit_permissions


class SharedPermissionsTests(APITestCase):

    def setUp(self):
        # Create a new User
        self.user = create_test_user(name='user', password='pw')
        self.test_project = Project.objects.create(title='testproj', owner=self.user)
        self.user.active_dataset = self.test_project

        self.client = APIClient()
        self.client.login(username='user', password='pw')
        # Test on the core.taggers ModelViewSet url
        self.basic_test_url = '/taggers/'


    def test_has_active_project_allow(self):
        '''Test if HasActiveProject returns True if a project is active'''
        self.user.profile.active_project = self.test_project
        self.user.save()
        response = self.client.get(self.basic_test_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def test_has_active_project_forbid(self):
        '''Test if HasActiveProject returns False if a project is not active'''
        response = self.client.get(self.basic_test_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Compare message, in case its some different permission that got denied
        self.assertEqual(str(response.data['detail']), toolkit_permissions.HasActiveProject.message)
