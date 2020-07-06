from io import BytesIO

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

        cls.group_url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/regex_tagger_groups/'

        cls.tagger_id = None

    def setUp(self):
        self.client.login(username='user', password='pw')


    def test(self):
        self.run_test_regex_tagger_create()
        self.run_test_regex_tagger_tag_text()
        self.run_test_regex_tagger_tag_texts()
        self.run_test_regex_tagger_export_import()
        self.run_test_regex_tagger_multitag()

        self.run_test_regex_group_create()


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
            "return_fuzzy_match": False
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


    def run_test_regex_tagger_tag_texts(self):
        '''Tests RegexTagger tagging.'''
        tagger_url = f'{self.url}{self.tagger_id}/tag_texts/'

        ### test matching text
        payload = {
            "texts": ["selles tekstis on mõrtsukas jossif stalini nimi", "selles tekstis on onkel adolf hitler"],
            "return_fuzzy_match": False
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()[0]) == 2

        ### test non-matching text
        payload = {
            "texts": ["selles tekstis pole nimesid"],
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_no_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()) == 0


    def run_test_regex_tagger_export_import(self):
        '''Tests RegexTagger export and import.'''
        export_url = f'{self.url}{self.tagger_id}/export_model/'
        # get model zip
        response = self.client.get(export_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ### test matching text
        tagger_url = f'{self.url}{self.tagger_id}/tag_texts/'
        payload = {
            "texts": ["selles tekstis on mõrtsukas jossif stalini nimi", "selles tekstis on onkel adolf hitler"],
            "return_fuzzy_match": False
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()[0]) == 2


    def run_test_regex_tagger_multitag(self):
        '''Tests multitag endpoint.'''
        tagger_url = f'{self.url}multitag_text/'
         ### test matching text
        payload = {
            "text": ["selles tekstis on mõrtsukas jossif stalini nimi", "selles tekstis on onkel adolf hitler"],
            "return_fuzzy_match": True
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()[0]) == 4


    def run_test_regex_group_create(self):
        '''Tests RegexTaggerGroup creation.'''
        payload = {
            "description": "test group",
            "regex_taggers": [1,2]
        }
        response = self.client.post(self.group_url, payload)
        print_output('test_regex_tagger_group_create:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tagger_group_id = response.data['id']

        ### test predicting

        tagger_url = f'{self.group_url}multitag_text/'
        payload = {
            "text": "selles tekstis on mõrtsukas jossif stalini nimi",
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_group_multitag_text:response.data', response.data)
