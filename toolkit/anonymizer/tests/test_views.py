from io import BytesIO
import json

from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.core.project.models import Project
from toolkit.tools.utils_for_tests import project_creation
from toolkit.tools.utils_for_tests import create_test_user, print_output
from toolkit.test_settings import TEST_INDEX, TEST_VERSION_PREFIX

class AnonymizerViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_user('user', 'my@email.com', 'pw')
        cls.project = project_creation("AnonymizerTestProject", TEST_INDEX, cls.user)
        cls.project.users.add(cls.user)
        cls.url = f'{TEST_VERSION_PREFIX}/projects/{cls.project.id}/anonymizers/'

        cls.anonymizer_id = None

    def setUp(self):
        self.client.login(username='user', password='pw')


    def test(self):
        self.run_test_anonymizer_create()
        self.run_test_anonymizer_anonymize_text()
        self.run_test_anonymizer_anonymize_texts()
        self.run_test_anonymizer_export_import()


    def run_test_anonymizer_create(self):
        '''Tests Anonymizer creation.'''
        payload = {
            "description": "TestAnonymizer"
        }

        response = self.client.post(self.url, payload)
        print_output('test_anonymizer_create:response.data', response.data)
        created_id = response.data['id']

        self.anonymizer_id = created_id

        # Check if lexicon gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


    def run_test_anonymizer_anonymize_text(self):
        '''Tests Anonymizer text anonymization.'''
        anonymizer_url = f'{self.url}{self.anonymizer_id}/anonymize_text/'

        ###test anonymizing text
        payload = {
            "text": "selles tekstis on mõrtsukas Jossif Stalini nimi",
            "names": ["Stalin, Jossif"]
        }
        response = self.client.post(anonymizer_url, payload)
        print_output('test_anonymizer_anonymized_text:response.data', response.data)
        assert len(response.json()) > 0


    def run_test_anonymizer_anonymize_texts(self):
        '''Tests Anonymizer multiple texts anonymization.'''
        anonymizer_url = f'{self.url}{self.anonymizer_id}/anonymize_texts/'

        ### test anonymizing texts
        payload = {
            "texts": ["selles tekstis on mõrtsukas Jossif Stalini nimi", "selles tekstis on onkel Adolf Hitler"],
            "names": ["Stalin, Jossif", "Hitler, Adolf"],
            "consistent_replacement": True
        }
        response = self.client.post(anonymizer_url, payload)
        print_output('test_anonymizer_anonymized_texts:response.data', response.data)
        # check if respnose not empy
        assert len(response.json()[0]) > 0


    def run_test_anonymizer_export_import(self):
        '''Tests Anonymizer export and import.'''
        export_url = f'{self.url}{self.anonymizer_id}/export_model/'
        # get model zip
        response = self.client.get(export_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ### test anonymizing text
        anonymizer_url = f'{self.url}{self.anonymizer_id}/anonymize_texts/'
        payload = {
            "texts": ["selles tekstis on mõrtsukas Jossif Stalini nimi", "selles tekstis on onkel Adolf Hitler"],
            "names": ["Stalin, Jossif", "Hitler, Adolf"]
        }
        response = self.client.post(anonymizer_url, payload)
        print_output('test_anonymizer_anonymized_texts:response.data', response.data)
        # check if response not empty
        assert len(response.json()[0]) > 0
