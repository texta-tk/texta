# Create your tests here.
import pathlib

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.test_settings import TEST_INDEX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class TestDocparserAPIView(APITestCase):

    def setUp(self) -> None:
        self.user = create_test_user('Owner', 'my@email.com', 'pw')
        self.unauthorized_user = create_test_user('unauthorized', 'my@email.com', 'pw')

        self.project = project_creation("test_doc_parser", index_title=None, author=self.user)
        self.project.users.add(self.user)
        self.unauth_project = project_creation("unauth_project", index_title=None, author=self.user)

        self.file = SimpleUploadedFile("text.txt", b"file_content", content_type="text/html")
        self.client.login(username='Owner', password='pw')
        self._basic_pipeline_functionality()


    def _basic_pipeline_functionality(self):
        url = reverse("v1:docparser")
        payload = {
            "file": self.file,
            "project_id": self.project.pk,
            "indices": [TEST_INDEX]
        }
        response = self.client.post(url, data=payload)
        print_output("_basic_pipeline_functionality:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_file_appearing_in_proper_structure(self):
        path = pathlib.Path(settings.RELATIVE_PROJECT_DATA_PATH) / str(self.project.pk) / "docparser" / "text.txt"
        print_output("test_file_appearing_in_proper_structure", path.exists())
        self.assertTrue(path.exists())


    def test_being_rejected_without_login(self):
        url = reverse("v1:docparser")
        self.client.logout()
        payload = {
            "file": self.file,
            "project_id": self.project.pk,
            "indices": [TEST_INDEX]
        }
        response = self.client.post(url, data=payload)
        print_output("test_being_rejected_without_login:response.data", response.data)
        response_code = response.status_code
        print_output("test_being_rejected_without_login:response.status_code", response_code)

        self.assertTrue((response_code == status.HTTP_403_FORBIDDEN) or (response_code == status.HTTP_401_UNAUTHORIZED))
        self.client.login(username="Owner", password="pw")


    def test_being_rejected_with_wrong_project_id(self):
        url = reverse("v1:docparser")
        payload = {
            "file": self.file,
            "project_id": self.unauth_project.pk,
            "indices": [TEST_INDEX]
        }
        response = self.client.post(url, data=payload)
        print_output("test_being_rejected_with_wrong_project_id:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)


    def test_indices_being_added_into_the_project(self):
        project = Project.objects.get(pk=self.project.pk)
        indices = project.indices.all()
        added_index = indices.filter(name=TEST_INDEX)
        self.assertTrue(added_index.count() == 1)
        print_output("test_indices_being_added_into_the_project", True)


    def test_that_serving_media_works_for_authenticated_users(self):
        url = reverse("protected_serve", kwargs={"project_id": self.project.pk, "application": "docparser", "file_name": "text.txt"})
        response = self.client.get(url)
        print_output("test_that_serving_media_works_for_authenticated_users", True)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def test_that_serving_media_doesnt_work_for_unauthenticated_users(self):
        self.client.logout()
        url = reverse("protected_serve", kwargs={"project_id": self.project.pk, "application": "docparser", "file_name": "text.txt"})
        response = self.client.get(url)
        print_output("test_that_serving_media_doesnt_work_for_unauthenticated_users", True)
        self.assertTrue(response.status_code == status.HTTP_302_FOUND)
        self.client.login(username='Owner', password='pw')  # Login again for the sake of other tests.


    def test_media_access_for_unauthorized_projects(self):
        self.client.login(username="unauthorized", password="pw")
        url = reverse("protected_serve", kwargs={"project_id": self.project.pk, "application": "docparser", "file_name": "text.txt"})
        response = self.client.get(url)
        print_output("test_media_access_for_unauthorized_projects", True)
        self.assertTrue(response.status_code == status.HTTP_403_FORBIDDEN)
        self.client.logout()
        self.client.login(username='Owner', password='pw')  # Login again for the sake of other tests.
