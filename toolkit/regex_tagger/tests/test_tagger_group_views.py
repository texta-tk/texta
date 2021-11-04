import json
from typing import List

import elasticsearch_dsl
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from texta_elastic.core import ElasticCore
from toolkit.helper_functions import reindex_test_dataset
from toolkit.regex_tagger.models import RegexTagger, RegexTaggerGroup
from toolkit.settings import TEXTA_TAGS_KEY
from toolkit.test_settings import TEST_FIELD, TEST_INTEGER_FIELD, VERSION_NAMESPACE
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


    def _set_up_project(self):
        self.user = create_test_user('tg_user', 'my@email.com', 'pw')
        self.project = project_creation("RegexGroupTaggerTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.client.login(username='tg_user', password='pw')


    def _set_up_tagger_group(self, payloads: List[dict], tg_description: str):
        ids = []

        tagger_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        for payload in payloads:
            response = self.client.post(tagger_url, payload)
            ids.append(int(response.data["id"]))

        tg_payload = {
            "description": tg_description,
            "regex_taggers": ids
        }
        response = self.client.post(self.tagger_group_list_url, tg_payload)
        ids.append(int(response.data["id"]))

        return ids


    def tearDown(self) -> None:
        from texta_elastic.core import ElasticCore
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])


    def setUp(self) -> None:
        self.test_index_name = reindex_test_dataset()
        self._set_up_project()
        self.tagger_group_list_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-list", kwargs={"project_pk": self.project.pk})
        self.tagger_list_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-list", kwargs={"project_pk": self.project.pk})

        self.police_id, self.medic_id, self.firefighter_id, self.emergency_tagger_group_id = self._set_up_tagger_group([
            {"description": "politsei", "lexicon": ["varas", "röövel", "vägivald", "pettus"]},
            {"description": "kiirabi", "lexicon": ["haav", "vigastus", "trauma"]},
            {"description": "tuletõrje", "lexicon": ["põleng", "õnnetus"]}
        ], "Hädaabi")

        self.stomach_pain_id, self.headache_id, self.pain_tagger_group_id = self._set_up_tagger_group([
            {"description": "peavalu", "lexicon": ["migreen", "migreenid", "migreeni", "peavalu", "pea valutab", "valutab pea"]},
            {"description": "kõhuvalu", "lexicon": ["kõht valutab", "kõhuvalu", "valutab kõht"]},
        ], "Valu")


    def test_regex_tagger_group_tag_text(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-text", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
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


    def test_regex_tagger_group_tag_text_empty(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-text",
                      kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        response = self.client.post(url, {
            "text": ""})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print_output('test_regex_tagger_group_tag_text_empty:response.data', response.data)

        self.assertEqual(response.data["result"], False)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("tagger_group_tag" in response.data)
        self.assertTrue("text" in response.data)
        self.assertTrue(len(response.data["matches"]) == 0)


    def test_regex_tagger_group_multitag_text(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-multitag-text", kwargs={"project_pk": self.project.pk})
        payload = {
            "text": "Miks varas sai haavata!?",
            "taggers": [tagger.pk for tagger in RegexTaggerGroup.objects.filter(project__id=self.project.pk)]
        }
        response = self.client.post(url, payload)
        tg = RegexTaggerGroup.objects.get(pk=self.emergency_tagger_group_id)
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
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-apply-tagger-group", kwargs={"project_pk": self.project.pk, "pk": tg_id})
        response = self.client.post(url, {"description": "Test Run", "fields": [TEST_FIELD], "indices": [{"name": self.test_index_name}]})
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        s = elasticsearch_dsl.Search(index=self.test_index_name, using=ec.es)
        has_group_fact = False
        for hit in s.scan():
            facts = hit.to_dict().get("texta_facts", [])
            for fact in facts:
                if fact["fact"] == tg_description:
                    has_group_fact = True

        self.assertTrue(has_group_fact)
        print_output('test_applying_the_regex_tagger_group_to_the_index:response.data', response.data)


    def test_regex_tagger_group_tagging_nested_doc(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
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
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        response = self.client.post(url, {"fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("tagger_group_id" in response.data)
        self.assertTrue("tagger_group_tag" in response.data)
        self.assertTrue("matches" in response.data)
        self.assertTrue("document" in response.data and isinstance(response.data["document"], dict))
        self.assertTrue(response.data["result"] is True or response.data["result"] is False)
        print_output('test_regex_tagger_group_tag_random_doc:response.data', response.data)


    def test_editing_another_tagger_into_the_group(self):
        tagger_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        military_tagger = self.client.post(tagger_url, {
            "description": "sõjavägi",
            "lexicon": ["luure", "sõdur", "õppus", "staap"]
        }, format="json").data

        tagger_group_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-detail", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        update_response = self.client.patch(tagger_group_url, {"regex_taggers": [military_tagger["id"]]}, format="json")
        self.assertTrue(update_response.status_code == status.HTTP_200_OK)
        self.assertTrue(update_response.data["regex_taggers"] == [military_tagger["id"]])
        print_output('test_editing_another_tagger_into_the_group:response.data', update_response.data)


    def test_that_non_text_fields_are_handled_properly(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        response = self.client.post(url, {"fields": [TEST_INTEGER_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["matches"] == [] and response.data["result"] is False)
        print_output("test_that_non_text_fields_are_handled_properly:response.data", response.data)


    def test_tagging_documents_with_no_matches(self):
        tagger_group_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        payload = {
            "docs": [{"text": "miks ei tulnud mulle politseinikud appi!"}, {"text_2": {"text": "Kõik on politseinike süü!"}}],
            "fields": ["text", "text_2.text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        print_output("test_tagging_documents_with_no_matches::response.data", response.data)
        first_item, second_item = response.data
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("text" in first_item)
        self.assertTrue("text_2" in second_item and "text" in second_item["text_2"])
        self.assertTrue(TEXTA_TAGS_KEY in first_item and TEXTA_TAGS_KEY in second_item)


    def test_tagging_documents_with_matches(self):
        tagger_group_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        payload = {
            "docs": [{"text": "see varas oli süüdi!"}, {"text_2": {"text": "See põleng on kohutav!"}}],
            "fields": ["text", "text_2.text"]
        }

        response = self.client.post(tagger_group_url, data=payload, format="json")
        print_output("test_tagging_documents_with_matches::response.data", response.data)
        first_item, second_item = response.data
        first_facts, second_facts = first_item[TEXTA_TAGS_KEY], second_item[TEXTA_TAGS_KEY]
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("text" in first_item)
        self.assertTrue("text_2" in second_item and "text" in second_item["text_2"])
        self.assertTrue(TEXTA_TAGS_KEY in first_item and TEXTA_TAGS_KEY in second_item)
        self.assertTrue(len(first_facts) == 1 and len(second_facts) == 1)

        fact = first_item[TEXTA_TAGS_KEY][0]
        source = json.loads(fact["source"])
        self.assertTrue(fact["fact"] == "Hädaabi")
        self.assertTrue(fact["str_val"] == "politsei")
        self.assertTrue("regextagger_id" in source and source["regextagger_id"] == self.police_id)
        self.assertTrue("regextaggergroup_id" in source and source["regextaggergroup_id"] == self.emergency_tagger_group_id)

        fact = second_item[TEXTA_TAGS_KEY][0]
        source = json.loads(fact["source"])
        self.assertTrue(fact["fact"] == "Hädaabi")
        self.assertTrue(fact["str_val"] == "tuletõrje")
        self.assertTrue("regextagger_id" in source and source["regextagger_id"] == self.firefighter_id)
        self.assertTrue("regextaggergroup_id" in source and source["regextaggergroup_id"] == self.emergency_tagger_group_id)


    def test_that_tagging_tagged_documents_wont_result_in_duplicate_facts(self):
        tagger_group_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        fact = {
            'doc_path': 'text',
            'fact': 'Hädaabi',
            'source': json.dumps({"regextaggergroup_id": self.emergency_tagger_group_id, "regextagger_id": self.police_id}),
            'spans': '[[4, 9]]',
            'str_val': 'politsei'
        }

        payload = {
            "docs": [{"text": "see varas oli süüdi!", TEXTA_TAGS_KEY: [fact]}],
            "fields": ["text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        print_output("test_that_tagging_tagged_documents_wont_result_in_duplicate_facts::response.data", response.data)

        first_match = response.data[0]
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("text" in first_match)
        facts = first_match[TEXTA_TAGS_KEY]
        self.assertTrue(len(facts) == 1)


    def test_parsing_docs_where_field_is_missing(self):
        tagger_group_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-tag-docs", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        payload = {
            "docs": [{"text": "see varas oli süüdi!"}, {"tekst": "see põleng oli varas!"}],
            "fields": ["text"]
        }
        response = self.client.post(tagger_group_url, data=payload, format="json")
        print_output("test_parsing_docs_where_field_is_missing::response.data", response.data)

        self.assertTrue(response.status_code == status.HTTP_200_OK)
        facts = response.data[0][TEXTA_TAGS_KEY]
        self.assertTrue(len(facts) == 1)


    def test_multitag_docs_works_on_multiple_groups(self):
        payload = {
            "docs": [{"text": "See varas tekitab ikka korraliku peavalu!"}, {"text": "Põleng tappis kolm, neljandal valutab kõht."}],
            "fields": ["text"],
            "tagger_groups": [self.emergency_tagger_group_id, self.pain_tagger_group_id]
        }
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-multitag-docs", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_multitag_docs_works_on_multiple_groups::response.data", response.data)

        self.assertTrue(response.status_code == status.HTTP_200_OK)
        first_doc, second_doc = response.data
        self.assertTrue("text" in first_doc and "text" in second_doc)  # Check that original doc is still there.

        facts = []
        for document in response.data:
            for fact in document[TEXTA_TAGS_KEY]:
                facts.append(fact)

        str_vals = [fact["str_val"] for fact in facts]
        tags = [fact["fact"] for fact in facts]

        self.assertTrue({"politsei", "tuletõrje", "kõhuvalu", "peavalu"} == set(str_vals))
        self.assertTrue({"Valu", "Hädaabi"} == set(tags))


    def test_multitag_docs_handles_empty_field(self):
        payload = {
            "docs": [{"texta": "See varas tekitab ikka korraliku peavalu!"}, {"texta": "Põleng tappis kolm, neljandal valutab kõht."}],
            "fields": ["text"],
            "tagger_groups": [self.emergency_tagger_group_id, self.pain_tagger_group_id]
        }
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-multitag-docs", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, data=payload, format="json")
        print_output("test_multitag_docs_handles_empty_field::response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        first_doc, second_doc = response.data
        self.assertTrue("texta" in first_doc and "texta" in second_doc)  # Check that original doc is still there.
        self.assertTrue(first_doc[TEXTA_TAGS_KEY] == [] and second_doc[TEXTA_TAGS_KEY] == [])  # Check for no matches.


    def test_normal_field_edit_in_tagger_group(self):
        payload = {"description": "hädaabi"}
        tagger_group_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger_group-detail", kwargs={"project_pk": self.project.pk, "pk": self.emergency_tagger_group_id})
        response = self.client.patch(tagger_group_url, payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["description"] == "hädaabi")
