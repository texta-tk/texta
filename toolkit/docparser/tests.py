# Create your tests here.
import os
import pathlib

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from texta_elastic.core import ElasticCore

from toolkit.core.project.models import Project
from toolkit.helper_functions import reindex_test_dataset
from toolkit.test_settings import VERSION_NAMESPACE
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class TestDocparserAPIView(APITestCase):

    def setUp(self) -> None:
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('Owner', 'my@email.com', 'pw')
        self.unauthorized_user = create_test_user('unauthorized', 'my@email.com', 'pw')
        self.file_name = "d41d8cd98f00b204e9800998ecf8427e.txt"

        self.project = project_creation("test_doc_parser", index_title=None, author=self.user)
        self.project.users.add(self.user)
        self.unauth_project = project_creation("unauth_project", index_title=None, author=self.user)

        self.file = SimpleUploadedFile("text.txt", b"file_content", content_type="text/html")
        self.client.login(username='Owner', password='pw')
        self._basic_pipeline_functionality()
        self.file_path = self._get_file_path()
        self.ec = ElasticCore()


    def tearDown(self) -> None:
        self.ec.delete_index(index=self.test_index_name, ignore=[400, 404])


    def _get_file_path(self):
        path = pathlib.Path(settings.RELATIVE_PROJECT_DATA_PATH) / str(self.project.pk) / "docparser" / self.file_name
        return path


    def _basic_pipeline_functionality(self):
        url = reverse(f"{VERSION_NAMESPACE}:docparser")
        payload = {
            "file": self.file,
            "project_id": self.project.pk,
            "indices": [self.test_index_name],
            "file_name": self.file_name
        }
        response = self.client.post(url, data=payload)
        print_output("_basic_pipeline_functionality:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_file_appearing_in_proper_structure(self):
        print_output("test_file_appearing_in_proper_structure", self.file_path.exists())
        self.assertTrue(self.file_path.exists())


    def test_being_rejected_without_login(self):
        url = reverse(f"{VERSION_NAMESPACE}:docparser")
        self.client.logout()
        payload = {
            "file": self.file,
            "project_id": self.project.pk,
            "indices": [self.test_index_name]
        }
        response = self.client.post(url, data=payload)
        print_output("test_being_rejected_without_login:response.data", response.data)
        response_code = response.status_code
        print_output("test_being_rejected_without_login:response.status_code", response_code)

        self.assertTrue((response_code == status.HTTP_403_FORBIDDEN) or (response_code == status.HTTP_401_UNAUTHORIZED))


    def test_being_rejected_with_wrong_project_id(self):
        url = reverse(f"{VERSION_NAMESPACE}:docparser")
        payload = {
            "file": self.file,
            "project_id": self.unauth_project.pk,
            "indices": [self.test_index_name]
        }
        self.unauth_project.users.remove(self.user)
        response = self.client.post(url, data=payload)
        print_output("test_being_rejected_with_wrong_project_id:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_indices_being_added_into_the_project(self):
        project = Project.objects.get(pk=self.project.pk)
        indices = project.indices.all()
        added_index = indices.filter(name=self.test_index_name)
        self.assertTrue(added_index.count() == 1)
        print_output("test_indices_being_added_into_the_project", True)


    def test_that_serving_media_works_for_authenticated_users(self):
        file_name = self.file_path.name
        url = reverse("protected_serve", kwargs={"project_id": self.project.pk, "application": "docparser", "file_name": file_name})
        response = self.client.get(url)
        print_output("test_that_serving_media_works_for_authenticated_users", True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def test_that_serving_media_doesnt_work_for_unauthenticated_users(self):
        self.client.logout()
        file_name = self.file_path.name
        url = reverse("protected_serve", kwargs={"project_id": self.project.pk, "application": "docparser", "file_name": file_name})
        response = self.client.get(url)
        print_output("test_that_serving_media_doesnt_work_for_unauthenticated_users", True)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_media_access_for_unauthorized_projects(self):
        self.client.login(username="unauthorized", password="pw")
        file_name = self.file_path.name
        url = reverse("protected_serve", kwargs={"project_id": self.project.pk, "application": "docparser", "file_name": file_name})
        response = self.client.get(url)
        print_output("test_media_access_for_unauthorized_projects", True)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN or response.status_code == status.HTTP_401_UNAUTHORIZED)


    def test_that_saved_file_size_isnt_zero(self):
        """
        Necessary because of a prior bug where the wrapper would save a file
        with the right name but not it's contents.
        """
        import time
        time.sleep(10)
        file_size = os.path.getsize(self.file_path)
        self.assertTrue(file_size > 1)
        print_output("test_that_saved_file_size_isnt_zero::file_size:int", file_size)


    def test_payload_with_empty_indices(self):
        url = reverse(f"{VERSION_NAMESPACE}:docparser")
        payload = {
            "file": SimpleUploadedFile("text.txt", b"file_content", content_type="text/html"),
            "project_id": self.project.pk,
            "file_name": self.file_name
        }
        response = self.client.post(url, data=payload)
        print_output("_basic_pipeline_functionality:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
