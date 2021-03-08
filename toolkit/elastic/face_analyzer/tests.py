import json
from unittest import skipIf

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.elastic.tools.core import ElasticCore
from toolkit.test_settings import *
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class FaceAnalyzerViewTests(APITransactionTestCase):

    def setUp(self):
        ''' user needs to be admin, because of changed indices permissions '''
        self.default_password = 'pw'
        self.default_username = 'indexOwner'
        self.user = create_test_user(self.default_username, 'my@email.com', self.default_password)
        # create admin to test indices removal from project
        self.admin = create_test_user(name='admin', password='1234')
        self.admin.is_superuser = True
        self.admin.save()
        self.project = project_creation("FaceAnalyzerTestProject", [], self.user)
        self.project.users.add(self.user)

        self.client.login(username=self.default_username, password=self.default_password)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/face_analyzer/'


    def tearDown(self):
        ElasticCore().delete_index(TEST_FACE_ANALYZER_INDEX)


    @skipIf(ElasticCore().build_flavor() == "oss", "Vector support is only available past the Basic license!")
    def test_run(self):
        self.run_test_add_face()
        self.run_test_analyze_photo()


    def run_test_add_face(self):
        image = open(TEST_IMAGE_FILE_1, "rb")
        url = f"{self.url}add_face/"
        payload = {
            "index": TEST_FACE_ANALYZER_INDEX,
            "name": "KNOWN_FACE",
            "value": "John Not Doe",
            "image": image
        }
        response = self.client.post(url, payload)
        self.assertTrue("success" in response.data)


    def run_test_analyze_photo(self):
        image = open(TEST_IMAGE_FILE_2, "rb")
        payload = {
            "index": TEST_FACE_ANALYZER_INDEX,
            "image": image
        }
        response = self.client.post(self.url, payload)
        self.assertTrue("detected_faces" in response.data)
        self.assertTrue(len(response.data["detected_faces"]))
