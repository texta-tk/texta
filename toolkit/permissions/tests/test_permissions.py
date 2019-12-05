from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.urls import project_router
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_FIELD, TEST_INDEX


class ProjectPermissionsTests(APITestCase):


    def setUp(self):
        self.default_password = 'pw'
        self.admin = create_test_user(name='admin', password='1234')
        self.admin.is_superuser = True
        self.admin.save()
        self.owner = create_test_user(name='owner', password=self.default_password)
        self.project_user = create_test_user(name='project_user', password=self.default_password)
        self.user = create_test_user(name='user', password=self.default_password)

        self.project = Project.objects.create(title='testproj', owner=self.owner)
        self.project.users.add(self.project_user)

        self.client = APIClient()
        self.project_instance_url = f'/projects/{self.project.id}/'

    def test_all(self):
        registered_resources = [resource[0] for resource in project_router.registry]
        for resource in registered_resources:
            self.project_resource_url = f'/projects/{self.project.id}/{resource}/'
            self.run_with_users(self.access_project_resources, resource)
        self.run_with_users(self.access_project_instance_methods)
        self.run_with_users(self.update_project_fields)

    def run_with_users(self, func, resource=None):
        func(self.admin, '1234')
        # func(self.project.owner, self.default_password)
        if resource is None:
            func(self.project_user, self.default_password, UNSAFE_FORBIDDEN=True)
            func(self.user, self.default_password, SAFE_FORBIDDEN=True, UNSAFE_FORBIDDEN=True)
        else:
            func(self.project_user, self.default_password)
            func(self.user, self.default_password, SAFE_FORBIDDEN=True)

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
        responses = {'GET': get_response, 'PUT': self.client.put(url, get_response.data, format='json')}
        self.validate_safe_response(responses['GET'], url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)
        self.validate_unsafe_response(responses['PUT'], url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)

    def update_project_fields(self, username, password, SAFE_FORBIDDEN=False, UNSAFE_FORBIDDEN=False):
        url = self.project_instance_url
        self.client.login(username=username, password=password)
        self.update_title_and_indices(url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)
        self.add_user_to_project(url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)

    def update_title_and_indices(self, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN):
        get_response = self.client.get(url)
        get_response.data["indices"] =  {TEST_INDEX}
        get_response.data["title"] = "put_title"
        put_response = self.client.put(url, get_response.data, format='json')
        self.validate_unsafe_response(put_response, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)

    def add_user_to_project(self, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN):
        self.user_to_add = create_test_user(name=f'{username}_added_user', password=self.default_password)

        # if auth_user can't access the project go straight to validation
        get_res = self.client.get(url)
        if SAFE_FORBIDDEN is True and UNSAFE_FORBIDDEN is True:
            self.validate_unsafe_response(get_res, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)
        else:
            users = get_res.data['users']
            users.append(f'/users/{self.user_to_add.id}/')
            payload = {
                "title": "user_add_test",
                "users": users
            }
            add_response = self.client.put(url, payload, format='json')
            print_output("user_add: ", add_response.data)
            self.validate_unsafe_response(add_response, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN)

    def validate_safe_response(self, response, url, username, SAFE_FORBIDDEN, UNSAFE_FORBIDDEN):
        # admin & project_owner
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
        # admin & project_owner
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
