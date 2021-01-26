from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.test_settings import TEST_INDEX, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class LexiconViewsTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('user', 'my@email.com', 'pw')
        cls.project = project_creation("LexiconTestProject", TEST_INDEX, cls.user)
        cls.project.users.add(cls.user)
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/lexicons/'


    def setUp(self):
        self.client.login(username='user', password='pw')


    def test_run(self):
        self.run_lexicon_create(),
        self.run_lexicon_update(),
        self.run_defaults()


    def run_lexicon_create(self):
        '''Tests Lexicon creation.'''
        payload = {
            "description": "TestLexicon",
            "positives_used": ["esimene fraas", "teine fraas", "kolmas fraas leksikonile"],
            "positives_unused": ["lexicon_phrase not for model"],
            "negatives_used": ["negative_for_model"],
            "negatives_unused": ["random non_important phrase"]
        }
        response = self.client.post(self.url, payload)
        print_output('test_lexicon_create:response.data', response.data)
        created_id = response.data['id']

        # Check if lexicon gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue('esimene fraas' in response.data['positives_used'])

        # Check if created lexicon is accessible via API
        response = self.client.get(f'{self.url}{created_id}/')
        print_output('test_lexicon_retrieval:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('esimene fraas' in response.data['positives_used'])


    def run_lexicon_update(self):
        '''Tests Lexicon creation.'''
        payload = {
            "description": "TestLexicon",
            "positives_used": ["esimene fraas", "teine fraas"],
            "positives_unused": ["lexicon_phrase not for model", "kolmas fraas leksikonile"]
        }
        response = self.client.post(self.url, payload)
        print_output('test_lexicon_create:response.data', response.data)
        created_id = response.data['id']

        # Test update with PUT and PATCH
        payload = {
            "description": "PutTestLexicon",
            "positives_used": ["esimene fraas", "teine fraas", "neljas fraas"],
            "positives_unused": ["lexicon_phrase not for model changed", "kolmas fraas leksikonile"]
        }
        put_response = self.client.put(f'{self.url}{created_id}/', payload)
        print_output('test_lexicon_put:response.data', put_response.data)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)
        self.assertTrue('esimene fraas' in put_response.data['positives_used'])

        patch_response = self.client.patch(f'{self.url}{created_id}/', payload)
        print_output('test_lexicon_patch:response.data', patch_response.data)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertTrue('esimene fraas' in patch_response.data['positives_used'])

        # Check if updated lexicon is accessible via API
        response = self.client.get(f'{self.url}{created_id}/')
        print_output('test_lexicon_updated_retrieval:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue('neljas fraas' in response.data['positives_used'])


    def run_defaults(self):
        # perform_create test
        payload = {"description": "testDefaults"}
        response = self.client.post(self.url, payload)
        print_output('test_defaults_post', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # perform_update test
        created_id = response.data['id']
        put_response = self.client.put(f'{self.url}{created_id}/', payload)
        print_output('test_defaults_put', put_response.data)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)


