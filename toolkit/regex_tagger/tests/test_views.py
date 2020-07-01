from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import project_creation
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_INDEX, TEST_VERSION_PREFIX

class RegexTaggerViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user('user', 'my@email.com', 'pw')
        cls.project = project_creation("RegexTaggerTestProject", TEST_INDEX, cls.user)
        cls.project.users.add(cls.user)
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/regex_taggers/'

        cls.tagger_id = None

    def setUp(self):
        self.client.login(username='user', password='pw')


    def test(self):
        self.run_test_regex_tagger_create()
        self.run_test_regex_tagger_tag_text()


    def run_test_regex_tagger_create(self):
        '''Tests RegexTagger creation.'''
        payload = {
            "description": "TestRegexTagger",
            "lexicon": ["jossif stalin", "adolf hitler"],
            "counter_lexicon": ["benito mussolini"]
        }

        response = self.client.post(self.url, payload)
        print_output('test_regex_tagger_create:response.data', response.data)
        created_id = response.data['id']

        self.tagger_id = created_id

        # Check if lexicon gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


    def run_test_regex_tagger_tag_text(self):
        '''Tests RegexTagger tagging.'''
        tagger_url = f'{self.url}{self.tagger_id}/tag_text/'

        ###test matching text
        payload = {
            "text": "selles tekstis on mõrtsukas jossif stalini nimi",
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_text_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()) > 0

        ### test non-matching text
        payload = {
            "text": "selles tekstis pole nimesid",
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_text_no_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()) == 0
