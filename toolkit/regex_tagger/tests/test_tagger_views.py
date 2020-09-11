from io import BytesIO

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


class RegexTaggerViewTests(APITestCase):

    def setUp(self):
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("RegexTaggerTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/regex_taggers/'

        self.group_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/regex_tagger_groups/'

        self.tagger_id = None
        self.client.login(username='user', password='pw')

        ids = []
        payloads = [
            {"description": "politsei", "lexicon": ["varas", "röövel", "vägivald", "pettus"]},
            {"description": "kiirabi", "lexicon": ["haav", "vigastus", "trauma"]},
            {"description": "tuletõrje", "lexicon": ["põleng", "õnnetus"]}
        ]

        tagger_url = reverse("v1:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        for payload in payloads:
            response = self.client.post(tagger_url, payload)
            ids.append(int(response.data["id"]))

        self.police, self.medic, self.firefighter = ids


    def test(self):
        self.run_test_regex_tagger_create()
        self.run_test_regex_tagger_tag_text()
        self.run_test_regex_tagger_tag_texts()
        self.run_test_regex_tagger_export_import()
        self.run_test_regex_tagger_multitag()


    def run_test_regex_tagger_create(self):
        """Tests RegexTagger creation."""
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


    def test_tag_nested_doc(self):
        url = reverse("v1:regex_tagger-tag-doc", kwargs={"project_pk": self.project.pk, "pk": self.police})
        payload = {
            "doc": {
                "text": {"police": "Varas peeti kinni!"},
                "medics": "Ohver toimetati trauma tõttu haiglasse!"
            },
            "fields": ["text.police", "medics"]
        }
        response = self.client.post(url, payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertEqual(response.data["result"], True)
        self.assertTrue("tagger_id" in response.data)
        self.assertTrue("description" in response.data)

        matches = [match["str_val"] for match in response.data["matches"]]
        self.assertTrue("varas" in matches)
        print_output("test_tag_nested_doc:response.data", response.data)


    def test_tag_random_doc(self):
        url = reverse("v1:regex_tagger-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.police})
        response = self.client.post(url, {"fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("tagger_id" in response.data)
        self.assertTrue("description" in response.data)
        self.assertTrue("texts" in response.data and isinstance(response.data["texts"], list))
        self.assertTrue(response.data["result"] == True or response.data["result"] == False)
        print_output("test_tag_random_doc:response.data", response.data)


    def run_test_regex_tagger_tag_text(self):
        """Tests RegexTagger tagging."""
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
        """Tests RegexTagger tagging."""
        tagger_url = f'{self.url}{self.tagger_id}/tag_texts/'

        ### test matching text
        payload = {
            "texts": ["selles tekstis on mõrtsukas jossif stalini nimi", "selles tekstis on onkel adolf hitler"],
            "return_fuzzy_match": False
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()[0]) == 1
        assert len(response.json()) == 2

        ### test non-matching text
        payload = {
            "texts": ["selles tekstis pole nimesid", "selles ka mitte"],
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_no_match:response.data', response.data)
        # check if we found anything
        assert len(response.json()) == 2
        assert len(response.json()[0]) == 0


    def run_test_regex_tagger_export_import(self):
        """Tests RegexTagger export and import."""
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
        assert len(response.json()) == 2


    def run_test_regex_tagger_multitag(self):
        """Tests multitag endpoint."""
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
