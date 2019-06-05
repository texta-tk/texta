from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.project.models import Project
from toolkit.utils.utils_for_tests import create_test_user

class ProjectViewTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.owner = create_test_user('owner', 'my@email.com', 'pw')
        # User that has been included in the project
        cls.included_user = create_test_user('included', 'my2@email.com', 'pw')
        # Random user, that doesn't have permissions to the project
        cls.random_user = create_test_user('random', 'my3@email.com', 'pw')

        cls.project = Project.objects.create(title='testproj', owner=cls.owner)
        cls.project.users.set([cls.included_user])

        cls.activate_project_url = f'/projects/{cls.project.pk}/activate_project/'


    def test_owner_activate_project(self):
        '''Test project activation'''
        # Project Owner should be able to activate
        self.client.login(username='owner', password='pw')
        response = self.client.get(self.activate_project_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if the project includes the activated user
        self.assertTrue(self.owner.profile in self.project.activated_by.all())

    def test_included_activate_project(self):
        '''Test project activation'''
        # Included User should be able to activate
        self.client.login(username='included', password='pw')
        response = self.client.get(self.activate_project_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if the project includes the activated user
        self.assertTrue(self.included_user.profile in self.project.activated_by.all())


    def test_random_activate_project(self):
        '''Test project activation'''
        # Random unincluded User shouldn't be able to activate
        self.client.login(username='random', password='pw')
        response = self.client.get(self.activate_project_url)
        # Check if its 404, because if the user lacks permissions, the URL for that user will be 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # Check if the project includes the activated user
        self.assertTrue(self.random_user.profile not in self.project.activated_by.all())
