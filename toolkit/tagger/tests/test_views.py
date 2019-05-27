from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.project.models import Project
from toolkit.utils.utils_for_tests import create_test_user

class ProjectViewTests(APITestCase):

    def setUp(self):
        # Owner of the project
        self.owner = create_test_user('owner', 'my@email.com', 'pw')
        self.test_project = Project.objects.create(title='testproj', owner=self.owner)
        self.owner.profie.active_project = self.test.project

        self.client = APIClient()
        self.create_tagger_url = f'/taggers/create/'
