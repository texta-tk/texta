from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import create_test_user
from toolkit import permissions as toolkit_permissions


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
        self.project.users.add(self.owner)
        self.project.users.add(self.project_user)
        self.client = APIClient()
        self.project_instance_url = f'/projects/{self.project.id}/'

    def test_all(self):
        for resource in ('lexicons', 'taggers', 'embeddings', 'embedding_clusters', 'tagger_groups'):
            self.project_resource_url = f'/projects/{self.project.id}/{resource}/'
            self.run_with_users(self.access_project_resources, resource)
        self.run_with_users(self.access_project_instance_methods)
        self.run_with_users(self.update_project_fields)

    def run_with_users(self, func, resource=None):
        func(self.admin, '1234')
        func(self.project.owner, self.default_password)
        if resource is None:
            func(self.project_user, self.default_password, UNSAFE_FORBIDDEN=True)
            func(self.user, self.default_password, SAFE_FORBIDDEN=True, UNSAFE_FORBIDDEN=True)
        else:
            func(self.project_user, self.default_password)
            func(self.user, self.default_password, fail=True)

    def access_project_resources(self, username, password, fail=False):
        url = self.project_resource_url
        self.client.login(username=username, password=password)
        response = self.client.get(url)
        if fail is True:
            return self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def access_project_instance_methods(self, username, password, SAFE_FORBIDDEN=False, UNSAFE_FORBIDDEN=False):
        '''F, F for owner,admin, F, T for p_user, F, F for non-member.'''
        url = self.project_instance_url
        self.client.login(username=username, password=password)
        get_response = self.client.get(url)
        responses = {'GET': get_response, 'PUT': self.client.put(url, get_response.data, format='json')}
        for response in list(responses.values()):
            if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is False:
                self.assertEqual(response.status_code, status.HTTP_200_OK)
            if SAFE_FORBIDDEN is True and UNSAFE_FORBIDDEN is True:
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is True:
            self.assertEqual(responses['GET'].status_code, status.HTTP_200_OK)
            self.assertEqual(responses['PUT'].status_code, status.HTTP_403_FORBIDDEN)

    def update_project_fields(self, username, password, SAFE_FORBIDDEN=False, UNSAFE_FORBIDDEN=False):
        url = self.project_instance_url
        self.client.login(username=username, password=password)
        response = self.client.get(url)
        response.data["indices"] =  {"texta_test_index"}
        response.data["title"] = "put_title"
        put_response = self.client.put(url, response.data, format='json')
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is False:
            self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        if SAFE_FORBIDDEN is True and UNSAFE_FORBIDDEN is True:
                self.assertEqual(put_response.status_code, status.HTTP_404_NOT_FOUND)
        if SAFE_FORBIDDEN is False and UNSAFE_FORBIDDEN is True:
            self.assertEqual(put_response.status_code, status.HTTP_403_FORBIDDEN)

    # TODO: implement owner, user put testing separately; affects existing tests.
