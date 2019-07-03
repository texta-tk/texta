from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient
from toolkit.core.project.models import Project
from toolkit.core.user_profile.models import UserProfile
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_INDEX
import json

class LexiconViewsTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('user', 'my@email.com', 'pw')
        cls.project = Project.objects.create(
            title='LexiconTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )
        cls.user.profile.activate_project(cls.project)



    def setUp(self):
        self.client.login(username='user', password='pw')


    def test_lexicon_create(self):
        '''Tests Lexicon creation.'''
        payload = {
            "description": "TestLexicon",
            "phrases": json.dumps(["esimene fraas", "teine fraas"]),
        }
        response = self.client.post('/lexicons/', payload)
        print_output('test_lexicon_create:response.data', response.data)
        created_id = response.data['id']
        # Check if lexicon gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('esimene fraas' in json.loads(response.data['phrases']))

        # Check if created lexicon is accessible via API
        response = self.client.get(f'/lexicons/{created_id}/')
        print_output('test_lexicon_retrieval:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('esimene fraas' in json.loads(response.data['phrases']))


    def test_lexicon_update(self):
        '''Tests Lexicon creation.'''
        payload = {
            "description": "TestLexicon",
            "phrases": json.dumps(["esimene fraas", "teine fraas"]),
        }
        response = self.client.post('/lexicons/', payload)
        print_output('test_lexicon_create:response.data', response.data)
        created_id = response.data['id']

        # Check if lexicon is nicely updated when using put
        payload = {
            "description": "TestLexicon",
            "phrases": json.dumps(["esimene fraas", "teine fraas", "kolmas fraas"]),
        }
        response = self.client.put(f'/lexicons/{created_id}/', payload)
        print_output('test_lexicon_update:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('esimene fraas' in json.loads(response.data['phrases']))

        # Check if updated lexicon is accessible via API
        response = self.client.get(f'/lexicons/{created_id}/')
        print_output('test_lexicon_updated_retrieval:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('kolmas fraas' in json.loads(response.data['phrases']))
