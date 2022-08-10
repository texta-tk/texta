import json
import uuid
from io import BytesIO
from time import sleep

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore

from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.helper_functions import reindex_test_dataset
from toolkit.regex_tagger.models import RegexTagger
from toolkit.test_settings import (TEST_FIELD, TEST_INTEGER_FIELD, TEST_QUERY, TEST_VERSION_PREFIX, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class RegexTaggerViewTests(APITransactionTestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('user', 'my@email.com', 'pw')
        self.project = project_creation("RegexTaggerTestProject", self.test_index_name, self.user)
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

        tagger_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        for payload in payloads:
            response = self.client.post(tagger_url, payload)
            self.assertTrue(response.status_code == status.HTTP_201_CREATED)
            ids.append(int(response.data["id"]))

        self.police, self.medic, self.firefighter = ids

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/elastic/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_regex_tagger_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying taggers",
            "indices": [self.test_index_name],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying tagger:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])


    def tearDown(self) -> None:
        ec = ElasticCore()
        res = ec.delete_index(self.test_index_copy)
        ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete [Regex Tagger] apply_taggers test index {self.test_index_copy}", res)


    def test(self):
        self.run_test_apply_tagger_to_index()
        self.run_test_regex_tagger_create()
        self.run_test_regex_tagger_duplicate()
        self.run_test_regex_tagger_tag_nested_doc()
        self.run_test_regex_tagger_tag_random_doc()
        self.run_test_regex_tagger_tag_text()
        self.run_test_regex_tagger_tag_texts()
        self.run_test_regex_tagger_export_import()
        self.run_test_regex_tagger_multitag_text()
        self.run_test_create_and_update_regex_tagger()
        self.run_test_that_non_text_fields_are_handled_properly()
        self.run_test_that_creating_taggers_with_invalid_regex_creates_validation_exception()


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


    def run_test_regex_tagger_duplicate(self):
        """Tests RegexTagger duplication."""
        duplication_url = f'{self.url}{self.tagger_id}/duplicate/'
        original_tagger_url = f'{self.url}{self.tagger_id}/'

        payload = {}

        response = self.client.post(duplication_url, payload)

        print_output('test_regex_tagger_duplicate:response.data', response.data)

        duplicated_tagger_id = response.data["duplicate_id"]
        duplicated_tagger_url = f'{self.url}{duplicated_tagger_id}/'

        original_tagger_response = self.client.get(original_tagger_url)
        duplicated_tagger_response = self.client.get(duplicated_tagger_url)

        print_output('test_regex_tagger_duplication_original_tagger:response.data', original_tagger_response.data)
        print_output('test_regex_tagger_duplication_duplicated_tagger:response.data', duplicated_tagger_response.data)

        different_fields = ["id", "url"]
        ignore_fields = ["author_username", "tagger_groups"]

        # Check if object is duplicated correctly with different id, url and description
        # but otherwise the same params (author_username and tagger_groups can be the same, but don't have to)
        for key in original_tagger_response.data:
            if key in ignore_fields:
                continue
            elif key in different_fields:
                self.assertTrue(original_tagger_response.data[key] != duplicated_tagger_response.data[key])
            elif key == "description":
                self.assertTrue(f'{original_tagger_response.data[key]}_copy' == duplicated_tagger_response.data[key])
            else:
                self.assertTrue(original_tagger_response.data[key] == duplicated_tagger_response.data[key])

        # Check if the duplication was successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)


    def run_test_regex_tagger_tag_nested_doc(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-tag-doc", kwargs={"project_pk": self.project.pk, "pk": self.police})
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
        self.assertTrue("tag" in response.data)

        matches = [match["str_val"] for match in response.data["matches"]]
        self.assertTrue("varas" in matches)
        print_output("test_regex_tagger_tag_nested_doc:response.data", response.data)


    def run_test_regex_tagger_tag_random_doc(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.police})
        response = self.client.post(url, {"indices": [{"name": self.test_index_name}], "fields": [TEST_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue("tagger_id" in response.data)
        self.assertTrue("tag" in response.data)
        self.assertTrue("document" in response.data and isinstance(response.data["document"], dict))
        self.assertTrue(response.data["result"] == True or response.data["result"] == False)
        self.assertTrue("matches" in response.data)
        print_output("test_regex_tagger_tag_random_doc:response.data", response.data)


    def run_test_regex_tagger_tag_text(self):
        """Tests RegexTagger tagging."""
        tagger_url = f'{self.url}{self.tagger_id}/tag_text/'

        ###test matching text
        payload = {
            "text": "selles tekstis on mõrtsukas jossif stalini nimi"
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_text_match:response.data', response.data)
        # check if we found anything
        self.assertTrue("tagger_id" in response.data)
        self.assertTrue("tag" in response.data)
        self.assertTrue("result" in response.data)
        self.assertTrue("matches" in response.data)
        self.assertTrue("text" in response.data)
        self.assertEqual(response.data["result"], True)
        self.assertEqual(len(response.data["matches"]), 1)
        fact = response.data["matches"][0]
        self.assertTrue("fact" in fact)
        self.assertTrue("str_val" in fact)
        self.assertTrue("spans" in fact)
        self.assertTrue("doc_path" in fact)
        source = json.loads(fact["source"])
        self.assertTrue("regextagger_id" in source)

        ### test non-matching text
        payload = {
            "text": "selles tekstis pole nimesid"
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_text_no_match:response.data', response.data)
        # check if we found anything
        self.assertTrue("tagger_id" in response.data)
        self.assertTrue("tag" in response.data)
        self.assertTrue("result" in response.data)
        self.assertTrue("matches" in response.data)
        self.assertEqual(response.data["result"], False)
        self.assertEqual(len(response.data["matches"]), 0)


    def run_test_regex_tagger_tag_texts(self):
        """Tests RegexTagger tagging."""
        tagger_url = f'{self.url}{self.tagger_id}/tag_texts/'

        ### test matching text
        payload = {
            "texts": ["selles tekstis on mõrtsukas jossif stalini nimi", "selles tekstis on onkel adolf hitler"]
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_match:response.data', response.data)
        # check if we found anything
        self.assertEqual(len(response.data), 2)
        self.assertTrue("tagger_id" in response.data[0])
        self.assertTrue("tag" in response.data[0])
        self.assertTrue("result" in response.data[0])
        self.assertTrue("matches" in response.data[0])
        self.assertEqual(response.data[0]["result"], True)
        self.assertEqual(response.data[1]["result"], True)
        self.assertEqual(len(response.data[0]["matches"]), 1)
        self.assertEqual(len(response.data[1]["matches"]), 1)

        ### test non-matching text
        payload = {
            "texts": ["selles tekstis pole nimesid", "selles ka mitte"]
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_tag_texts_no_match:response.data', response.data)
        # check if we found anything
        self.assertEqual(len(response.data), 2)
        self.assertTrue("tagger_id" in response.data[0])
        self.assertTrue("tag" in response.data[0])
        self.assertTrue("result" in response.data[0])
        self.assertTrue("matches" in response.data[0])
        self.assertEqual(response.data[0]["result"], False)
        self.assertEqual(response.data[1]["result"], False)
        self.assertEqual(len(response.data[0]["matches"]), 0)
        self.assertEqual(len(response.data[1]["matches"]), 0)


    def run_test_regex_tagger_export_import(self):
        """Tests RegexTagger export and import."""
        export_url = f'{self.url}{self.tagger_id}/export_model/'
        # get model zip
        response = self.client.get(export_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_regex_tagger_import_model:response.data', import_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ### test matching text
        tagger_url = f'{self.url}{self.tagger_id}/tag_texts/'
        payload = {
            "texts": ["selles tekstis on mõrtsukas jossif stalini nimi", "selles tekstis on onkel adolf hitler"]
        }
        response = self.client.post(tagger_url, payload)
        print_output('test_regex_tagger_imported_model_tag_texts_match:response.data', response.data)
        # check if we found anything
        self.assertEqual(len(response.json()), 2)


    def run_test_regex_tagger_multitag_text(self):
        """Tests multitag endpoint."""
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-multitag-text", kwargs={"project_pk": self.project.pk})
        # tagger_url = f'{self.url}multitag_text/'
        ### test matching text
        payloads = [
            {
                "text": "maja teisel korrusel toimus põleng ning ohver sai tõsiseid vigastusi.",
                "taggers": [self.police, self.medic, self.firefighter]
            },
            {
                "text": "maja teisel korrusel toimus põleng ning ohver sai tõsiseid vigastusi."
            },
        ]

        for payload in payloads:
            response = self.client.post(url, payload, format="json")
            print_output('test_regex_tagger_multitag_text:response.data', response.data)
            # check if we found anything
            tags = [res["tag"] for res in response.data]
            self.assertEqual(len(response.data), 2)
            self.assertTrue("tagger_id" in response.data[0])
            self.assertTrue("tag" in response.data[0])
            self.assertTrue("matches" in response.data[0])
            self.assertEqual(len(response.data[0]["matches"]), 1)
            self.assertEqual(len(response.data[1]["matches"]), 1)
            self.assertTrue("str_val" in response.data[0]["matches"][0])
            self.assertTrue("span" in response.data[0]["matches"][0])
            self.assertTrue("kiirabi" in tags)
            self.assertTrue("tuletõrje" in tags)


    def run_test_create_and_update_regex_tagger(self):
        payload = {
            "description": "TestRegexTagger",
            "lexicon": ["jossif stalin", "adolf hitler"],
            "counter_lexicon": ["benito mussolini"]
        }
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-list", kwargs={"project_pk": self.project.pk})
        response = self.client.post(url, payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)

        tagger_id = response.data["id"]
        detail_url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-detail", kwargs={"project_pk": self.project.pk, "pk": int(tagger_id)})
        update_response = self.client.patch(detail_url, {"lexicon": ["jossif stalin"]}, format="json")
        self.assertTrue(update_response.status_code == status.HTTP_200_OK)
        self.assertTrue(update_response.data["lexicon"] == ["jossif stalin"])
        print_output('test_regex_tagger_create_and_update:response.data', response.data)


    def run_test_that_non_text_fields_are_handled_properly(self):
        url = reverse(f"{VERSION_NAMESPACE}:regex_tagger-tag-random-doc", kwargs={"project_pk": self.project.pk, "pk": self.police})
        response = self.client.post(url, {"fields": [TEST_INTEGER_FIELD]}, format="json")
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.assertTrue(response.data["matches"] == [] and response.data["result"] is False)
        print_output("test_that_non_text_fields_are_handled_properly", response.data)


    def run_test_that_creating_taggers_with_invalid_regex_creates_validation_exception(self):
        invalid_payload = {
            "description": "TestRegexTagger",
            "lexicon": ["jossif stalin))", "adolf** hitler"],
            "counter_lexicon": ["benito** (mussolini"]
        }

        response = self.client.post(self.url, invalid_payload)
        print_output('test_regex_tagger_create_invalid_input:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue("lexicon" in response.data)
        self.assertTrue("counter_lexicon" in response.data)


    # There was a bug where when a RT was applied to an index, it would create a task inside it
    # which would throw an exception when duplicating since it included the task inside it.
    def _check_that_rt_that_has_been_applied_to_index_can_be_duplicated(self, rt_id: int):
        url = reverse("v2:regex_tagger-duplicate", kwargs={"project_pk": self.project.pk, "pk": rt_id})
        response = self.client.post(url, data={}, format="json")
        print_output("_check_that_rt_that_has_been_applied_to_index_can_be_duplicated:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)


    def run_test_apply_tagger_to_index(self):
        """Tests applying tagger to index using apply_to_index endpoint."""

        # Make sure reindexer task has finished
        task_object = self.reindexer_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('[Regex Tagger] test_apply_tagger_to_index: waiting for reindexer task to finish, current status:', task_object.status)
            sleep(2)

        tagger_payload = {
            "description": "LOLL",
            "lexicon": ["loll"],
            "counter_lexicon": ["päris"]
        }

        response = self.client.post(self.url, tagger_payload)
        print_output('[Regex Tagger] new regex tagger for applying on the index:response.data', response.data)
        created_id = response.data['id']

        self.tagger_id = created_id
        url = f'{self.url}{self.tagger_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "indices": [{"name": self.test_index_copy}],
            "fields": [TEST_FIELD]
        }
        response = self.client.post(url, payload, format='json')
        print_output('[Regex Tagger] test_apply_tagger_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = RegexTagger.objects.get(pk=self.tagger_id)

        # Wait til the task has finished
        task_object = tagger_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output("tagger object:", tagger_object.to_json())
            print_output('[Regex Tagger] test_apply_tagger_to_index: waiting for applying tagger task to finish, current status:', task_object.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution("LOLL")
        print_output("[Regex Tagger] test_apply_tagger_to_index:elastic aggerator results:", results)

        # Check if expected number if new facts is added
        fact_value_1 = "loll"
        fact_value_2 = "lollikindel"
        n_fact_value_1 = 28
        n_fact_value_2 = 1

        self.assertTrue(fact_value_1 in results)
        self.assertTrue(fact_value_2 in results)
        self.assertTrue(results[fact_value_1] == n_fact_value_1)
        self.assertTrue(results[fact_value_2] == n_fact_value_2)

        self._check_that_rt_that_has_been_applied_to_index_can_be_duplicated(created_id)
