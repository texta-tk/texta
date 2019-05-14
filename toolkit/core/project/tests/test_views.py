from django.urls import include, path, reverse
from django.contrib.auth.models import User

from rest_framework.test import APITestCase #, URLPatternsTestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.project.models import Project
from toolkit.utils.utils_for_tests import create_test_user

class ProjectViewTests(APITestCase):

    def setUp(self):
        # Owner of the project
        self.owner = create_test_user('owner', 'my@email.com', 'pw')
        # User that has been included in the project
        self.included_user = create_test_user('included', 'my2@email.com', 'pw')
        # Random user, that doesn't have permissions to the project
        self.random_user = create_test_user('random', 'my3@email.com', 'pw')

        self.test_project = Project.objects.create(title='testproj', owner=self.owner.profile)
        self.test_project.users.set([self.included_user.profile])

        self.client = APIClient()


    def test_activate_project(self):
        '''Test project activation'''
        url = f'/projects/{self.test_project.pk}/activate_project/'

        # Project Owner should be able to activate
        self.client.login(username='owner', password='pw')
        response = self.client.put(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Included User should be able to activate
        self.client.login(username='included', password='pw')
        response = self.client.put(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Random unincluded User shouldn't be able to activate
        self.client.login(username='random', password='pw')
        response = self.client.put(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
