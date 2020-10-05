import json

import elasticsearch_dsl
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.elastic.core import ElasticCore
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup
from toolkit.settings import TEXTA_TAGS_KEY
from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_INTEGER_FIELD
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


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


    def test_regex_tagger_group_tag_text(self):
        url = reverse("v1:regex_tagger_group-tag-text", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        response = self.client.post(url, {"text": "Eile kell 10 õhtul sisenes varas keemiatehasesse, tema hooletuse tõttu tekkis põleng!"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print_output('test_regex_tagger_group_tag_text:response.data', response.data)

        self.assertEqual(response.data["result"], True)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("tagger_group_tag" in response.data)
        self.assertTrue("text" in response.data)

        matches = []
        for tag in response.data["matches"]:
            self.assertTrue("fact" in tag)
            self.assertTrue("source" in tag)
            self.assertTrue("str_val" in tag)
            self.assertTrue("spans" in tag)
            self.assertTrue("doc_path" in tag)
            matches.append(tag["str_val"])
        self.assertTrue("politsei" in matches)
        self.assertTrue("tuletõrje" in matches)


    def test_regex_tagger_group_multitag_text(self):
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
        self.assertTrue(tag["tagger_group_tag"] == tg.description)
        self.assertTrue(tag["tags"][0]["tag"] == police_tagger.description)
        self.assertTrue(isinstance(response.data, list))

        print_output('test_regex_tagger_group_multitag_text:response.data', response.data)


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


    def test_regex_tagger_group_tagging_nested_doc(self):
        url = reverse("v1:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        payload = {
            "docs": [{
                "text": {"police": "Varas peeti kinni!"},
                "medics": "Ohver toimetati trauma tõttu haiglasse!"
            }],
            "fields": ["text.police", "medics"]
        }
        response = self.client.post(url, payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        doc = response.data[0]
        self.assertTrue(len(doc[TEXTA_TAGS_KEY]) == 2)
        print_output('test_regex_tagger_group_tagging_nested_doc:response.data', response.data)


    def test_regex_tagger_group_tag_random_doc(self):
        url = reverse("v1:regex_tagger_group-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        response = self.client.post(url, {"fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("tagger_group_tag" in response.data)
        self.assertTrue("matches" in response.data)
        self.assertTrue("document" in response.data and isinstance(response.data["document"], dict))
        self.assertTrue(response.data["result"] is True or response.data["result"] is False)
        print_output('test_regex_tagger_group_tag_random_doc:response.data', response.data)


    def test_editing_another_tagger_into_the_group(self):
        tagger_url = reverse("v1:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        military_tagger = self.client.post(tagger_url, {
            "description": "sõjavägi",
            "lexicon": ["luure", "sõdur", "õppus", "staap"]
        }, format="json").data

        tagger_group_url = reverse("v1:regex_tagger_group-detail", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        update_response = self.client.patch(tagger_group_url, {"regex_taggers": [military_tagger["id"]]}, format="json")
        self.assertTrue(update_response.status_code == status.HTTP_200_OK)
        self.assertTrue(update_response.data["regex_taggers"] == [military_tagger["id"]])
        print_output('test_editing_another_tagger_into_the_group:response.data', update_response.data)


    def test_that_non_text_fields_are_handled_properly(self):
        url = reverse("v1:regex_tagger_group-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        response = self.client.post(url, {"fields": [TEST_INTEGER_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["matches"] == [] and response.data["result"] is False)
        print_output("test_that_non_text_fields_are_handled_properly:response.data", response.data)


    def test_tagging_documents_with_no_matches(self):
        tagger_group_url = reverse("v1:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        payload = {
            "docs": [{"text": "miks ei tulnud mulle politseinikud appi!"}, {"text_2": {"text": "Kõik on politseinike süü!"}}],
            "fields": ["text", "text_2.text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        first_item, second_item = response.data
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("text" in first_item)
        self.assertTrue("text_2" in second_item and "text" in second_item["text_2"])
        self.assertTrue(TEXTA_TAGS_KEY in first_item and TEXTA_TAGS_KEY in second_item)


    def test_tagging_documents_with_matches(self):
        tagger_group_url = reverse("v1:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        payload = {
            "docs": [{"text": "see varas oli süüdi!"}, {"text_2": {"text": "See põleng on kohutav!"}}],
            "fields": ["text", "text_2.text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        first_item, second_item = response.data
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("text" in first_item)
        self.assertTrue("text_2" in second_item and "text" in second_item["text_2"])
        self.assertTrue(TEXTA_TAGS_KEY in first_item and TEXTA_TAGS_KEY in second_item)
        self.assertTrue(len(first_item[TEXTA_TAGS_KEY]) == 1 and len(second_item[TEXTA_TAGS_KEY]) == 1)

        self.assertTrue(first_item[TEXTA_TAGS_KEY][0]["fact"] == "Hädaabi")
        self.assertTrue(first_item[TEXTA_TAGS_KEY][0]["str_val"] == "politsei")
        source = json.loads(first_item[TEXTA_TAGS_KEY][0]["source"])
        self.assertTrue("regextagger_id" in source and source["regextagger_id"] == self.police)
        self.assertTrue("regextaggergroup_id" in source and source["regextaggergroup_id"] == self.tagger_group_id)

        self.assertTrue(second_item[TEXTA_TAGS_KEY][0]["fact"] == "Hädaabi")
        self.assertTrue(second_item[TEXTA_TAGS_KEY][0]["str_val"] == "tuletõrje")
        source = json.loads(second_item[TEXTA_TAGS_KEY][0]["source"])
        self.assertTrue("regextagger_id" in source and source["regextagger_id"] == self.firefighter)
        self.assertTrue("regextaggergroup_id" in source and source["regextaggergroup_id"] == self.tagger_group_id)


    def test_that_tagging_tagged_documents_wont_result_in_duplicate_facts(self):
        tagger_group_url = reverse("v1:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        fact = {
            'doc_path': 'text',
            'fact': 'Hädaabi',
            'source': json.dumps({"regextaggergroup_id": self.tagger_group_id, "regextagger_id": self.police}),
            'spans': '[[4, 9]]',
            'str_val': 'politsei'
        }

        payload = {
            "docs": [{"text": "see varas oli süüdi!", TEXTA_TAGS_KEY: [fact]}],
            "fields": ["text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("text" in response.data[0])
        self.assertTrue(len(response.data[0][TEXTA_TAGS_KEY]) == 1)


    def test_parsing_docs_where_field_is_missing(self):
        tagger_group_url = reverse("v1:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.tagger_group_id})
        payload = {
            "docs": [{"text": "see varas oli süüdi!"}, {"tekst": "see põleng oli varas!"}],
            "fields": ["text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(len(response.data[0][TEXTA_TAGS_KEY]) == 1)
