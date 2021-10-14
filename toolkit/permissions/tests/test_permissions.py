from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from toolkit.test_settings import TEST_INDEX, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation
from toolkit.urls_v2 import project_router


class ProjectPermissionsTests(APITestCase):

    def setUp(self):
        self.default_password = 'pw'
        self.admin = create_test_user(name='admin', password='1234')
        self.admin.is_superuser = True
        # self.admin.is_staff = True
        self.admin.save()
        self.project_user = create_test_user(name='project_user', password=self.default_password)
        self.user = create_test_user(name='user', password=self.default_password)

        self.project = project_creation("proj", TEST_INDEX, self.admin)
        self.project.users.add(self.project_user)

        self.client = APIClient()
        self.project_instance_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/'


    def test_all(self):
        registered_resources = [resource[0] for resource in project_router.registry if resource[0] != "index"]
        for resource in registered_resources:
            self.project_resource_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/{resource}/'
            self.run_with_users(self.access_project_resources, resource)
        self.run_with_users(self.access_health)
        self.run_with_users(self.access_project_instance_methods)


    def run_with_users(self, func, resource=None):
        func(self.admin, '1234')
        # func(self.project.owner, self.default_password)
        if resource is None:
            func(self.project_user, self.default_password, UNSAFE_FORBIDDEN=True)
            func(self.user, self.default_password, SAFE_FORBIDDEN=True, UNSAFE_FORBIDDEN=True)
        else:
            func(self.project_user, self.default_password)
            func(self.user, self.default_password, SAFE_FORBIDDEN=True)


    def access_health(self, username, password, SAFE_FORBIDDEN=False, UNSAFE_FORBIDDEN=False):
        """ all users, including non-auth can access /health """
        url = f'{TEST_VERSION_PREFIX}/health/'
        self.client.login(username=username, password=password)
        get_response = self.client.get(url)
        print_output(f"{username} access health", get_response.status_code)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)


    def access_project_resources(self, username, password, SAFE_FORBIDDEN=False):
        url = self.project_resource_url
        self.client.login(username=username, password=password)
        response = self.client.get(url)
        print_output(f'{username} access project resources at: {url}', response.status_code)
        if SAFE_FORBIDDEN is True:
            return self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def access_project_instance_methods(self, username, password, SAFE_FORBIDDEN=False, UNSAFE_FORBIDDEN=False):
        '''F, F for owner,admin, F, T for p_user, F, F for non-member.'''
        url = self.project_instance_url
        self.client.login(username=username, password=password)
        get_response = self.client.get(url)
        responses = {'GET': get_response}
        self.validate_safe_response(responses['GET'], url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)


    def validate_safe_response(self, response, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN):
        # admin
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is False:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print_output(f'{username} access project instance methods at: {url}', response.status_code)
        # auth_user
        if SAFE_FORBIDDEN is True and UNSAFE_FORBIDDEN is True:
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
            print_output(f'{username} access project instance methods at: {url}', response.status_code)
        # project_user has safe access, but not unsafe_access
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is True:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print_output(f'{username} access safe methods at: {url}', response.status_code)


    def validate_unsafe_response(self, response, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN):
        # admin
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is False:
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            print_output(f'{username} update permissions at: {url}', response.status_code)
        # project_user
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is True:
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            print_output(f'{username} update permissions at: {url}', response.status_code)
        # auth_user
        if SAFE_FORBIDDEN is True and UNSAFE_FORBIDDEN is True:
            print_output(f'{username} update permissions at: {url}', response.status_code)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
