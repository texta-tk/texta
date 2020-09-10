from io import BytesIO

import elasticsearch_dsl
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APITransactionTestCase

from toolkit.elastic.core import ElasticCore
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup
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
        assert len(response.json()[0]) == 2


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


@override_settings(CELERY_ALWAYS_EAGER=True)
class RegexGroupTaggerTests(APITransactionTestCase):

    def __create_tagger_group(self, tg_description: str, content: tuple):
        tagger_ids = []
        for tagger_description, lexicon in content:
            response = self.client.post(self.tagger_list_url, {"description": tagger_description, "lexicon": lexicon})
            tagger_ids.append(response.data["id"])

        tg_response = self.client.post(self.tagger_group_list_url, {"description": tg_description, "regex_taggers": tagger_ids})
        return tg_response.data["id"], tagger_ids


    def setUp(self) -> None:
        self.user = create_test_user('tg_user', 'my@email.com', 'pw')
        self.project = project_creation("RegexGroupTaggerTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.client.login(username='tg_user', password='pw')

        self.tagger_group_list_url = reverse("v1:regex_tagger_group-list", kwargs={"project_pk": self.project.pk})
        self.tagger_list_url = reverse("v1:regex_tagger-list", kwargs={"project_pk": self.project.pk})

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

        tg_payload = {
            "description": "Hädaabi",
            "regex_taggers": [self.police, self.medic, self.firefighter]
        }

        response = self.client.post(self.tagger_group_list_url, tg_payload)
        self.tagger_group_id = int(response.data["id"])


    def test_tagging_single_text(self):
        url = reverse("v1:regex_tagger_group-tag-text", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        response = self.client.post(url, {"text": "Eile kell 10 õhtul sisenes varas keemiatehasesse, tema hooletuse tõttu tekkis põleng!"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print_output('test_tagging_single_text:response.data', response.data)

        self.assertEqual(response.data["result"], True)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("description" in response.data)

        matches = [match["str_val"] for match in response.data["matches"]]
        self.assertTrue("varas" in matches)
        self.assertTrue("põleng" in matches)


    def test_tagging_a_list_of_texts(self):
        url = reverse("v1:regex_tagger_group-tag-texts", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        response = self.client.post(url, {"texts": ["Ettevõtte juhatuse liikme hobiks on pettus.", "Ohver läbis tugeva psühholoogilise tauma", "Pärnu maanteel toimus õnnetus."]})
        self.assertEqual(response.data["result"], True)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("description" in response.data)

        matches = [match["str_val"] for match in response.data["matches"]]
        self.assertTrue("pettus" in matches)
        self.assertTrue("õnnetus" in matches)

        print_output('test_tagging_a_list_of_texts:response.data', response.data)


    def test_multitag_functionality(self):
        url = reverse("v1:regex_tagger_group-multitag-text", kwargs={"project_pk": self.project.pk})
        payload = {
            "text": "Miks varas sai haavata!?",
            "taggers": [tagger.pk for tagger in RegexTaggerGroup.objects.filter(project__id=self.project.pk)]
        }
        response = self.client.post(url, payload)
        tg = RegexTaggerGroup.objects.get(pk=self.tagger_group_id)
        police_tagger = RegexTagger.objects.get(description="politsei")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        tag = response.data[0]
        self.assertTrue(tag["fact"] == tg.description)
        self.assertTrue(tag["tagger_description"] == police_tagger.description)
        self.assertTrue(isinstance(response.data, list))

        print_output('test_multitag_functionality:response.data', response.data)


    def test_applying_the_regex_tagger_group_to_the_index(self):
        ec = ElasticCore()
        tg_description = "toxic"
        tg_id, tagger_ids = self.__create_tagger_group("%s" % tg_description, (
            ("racism", ["juut", "neeger", "tõmmu"]),
            ("hate", ["pederast", "debiilik"])
        ))
        url = reverse("v1:regex_tagger_group-apply-tagger-group", kwargs={"project_pk": self.project.pk, "pk": tg_id})
        response = self.client.post(url, {"description": "Test Run", "fields": [TEST_FIELD], "indices": [{"name": TEST_INDEX}]})
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        s = elasticsearch_dsl.Search(index=TEST_INDEX, using=ec.es)
        has_group_fact = False
        for hit in s.scan():
            facts = hit.to_dict().get("texta_facts", [])
            for fact in facts:
                if fact["fact"] == tg_description:
                    has_group_fact = True

        self.assertTrue(has_group_fact)
        print_output('test_applying_the_regex_tagger_group_to_the_index:response.data', response.data)


    def test_tagging_nested_doc(self):
        url = reverse("v1:regex_tagger_group-tag-doc", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
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
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("description" in response.data)

        matches = [match["str_val"] for match in response.data["matches"]]
        self.assertTrue("varas" in matches)
        self.assertTrue("trauma" in matches)
        print_output('test_tagging_nested_doc:response.data', response.data)


    def test_tag_random_doc(self):
        url = reverse("v1:regex_tagger_group-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        response = self.client.post(url, {"fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("description" in response.data)
        self.assertTrue("texts" in response.data and isinstance(response.data["texts"], list))
        self.assertTrue(response.data["result"] is True or response.data["result"] is False)
        print_output('test_tag_random_doc:response.data', response.data)


    def test_editing_another_tagger_into_the_group(self):
        tagger_url = reverse("v1:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        military_tagger = self.client.post(tagger_url, {
            "description": "sõjavägi",
            "lexicon": ["luure", "sõdur", "õppus", "staap"]
        }, format="json").data

        tagger_group_url = reverse("v1:regex_tagger_group-detail", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        update_response = self.client.patch(tagger_group_url, {"regex_taggers": [military_tagger["id"]]}, format="json")
        self.assertTrue(update_response.status_code == status.HTTP_200_OK)
        print_output('test_editing_another_tagger_into_the_group:response.data', update_response.data)
