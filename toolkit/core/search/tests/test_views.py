from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.core.project.models import Project
from toolkit.core.user_profile.models import UserProfile
from toolkit.tools.utils_for_tests import project_creation
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_INDEX, TEST_VERSION_PREFIX

class UserProfileSignalsAndViewsTests(APITestCase):

    def setUp(self):
        # Create a new User
        self.user = create_test_user(name='user', password='pw')
        self.project = project_creation("testproj", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client = APIClient()
        self.client.login(username='user', password='pw')


    def test_creation(self):
        '''Tests if a saved search gets created properly.'''
        url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/searches/'
        payload = {"description":"test", "query":{"elasticsearchQuery":{"highlight":{"fields":{},"number_of_fragments":0,"post_tags":["<TEXTA_SEARCHER_HIGHLIGHT_END_TAG>"],"pre_tags":["<TEXTA_SEARCHER_HIGHLIGHT_START_TAG>"]},"query":{"bool":{"boost":1,"filter":[],"minimum_should_match":0,"must":[],"must_not":[],"should":[]}}},"highlight":{"fields":{},"number_of_fragments":0,"post_tags":["<TEXTA_SEARCHER_HIGHLIGHT_END_TAG>"],"pre_tags":["<TEXTA_SEARCHER_HIGHLIGHT_START_TAG>"]},"query":{"bool":{"boost":1,"filter":[],"minimum_should_match":0,"must":[],"must_not":[],"should":[]}}},"query_constraints":[]}
        response = self.client.post(url, payload, format='json')
        print_output("search_creation: ", response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('query' in response.data)
        self.assertTrue('query_constraints' in response.data)
        self.assertTrue('author' in response.data)
        self.assertTrue('project' in response.data)
