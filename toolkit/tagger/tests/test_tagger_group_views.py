import json
import pathlib
import uuid
from io import BytesIO
from time import sleep

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from toolkit.core.task.models import Task
from toolkit.elastic.reindexer.models import Reindexer
from toolkit.elastic.tools.aggregator import ElasticAggregator
from toolkit.elastic.tools.core import ElasticCore
from toolkit.elastic.tools.searcher import ElasticSearcher
from toolkit.helper_functions import reindex_test_dataset
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.test_settings import (TEST_FACT_NAME, TEST_FIELD, TEST_FIELD_CHOICE, TEST_KEEP_PLOT_FILES, TEST_QUERY, TEST_TAGGER_GROUP, TEST_VERSION_PREFIX, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerGroupViewTests(APITransactionTestCase):

    def setUp(self):
        # Owner of the project
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerGroupTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/tagger_groups/'
        self.test_tagger_group_id = None

        self.client.login(username='taggerOwner', password='pw')
        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_TAGGER_GROUP_NAME"
        self.new_fact_name_tag_limit = "TEST_TAGGER_GROUP_NAME_LIMITED_TAGS"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_tagger_group_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying tagger group",
            "indices": [self.test_index_name],
            "query": json.dumps(TEST_QUERY),
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying tagger group:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])

        self.test_imported_tagger_group_id = self.import_test_model(TEST_TAGGER_GROUP)


    def import_test_model(self, file_path: str):
        """Import models for testing."""
        print_output("Importing model from file:", file_path)
        files = {"file": open(file_path, "rb")}
        import_url = f'{self.url}import_model/'
        resp = self.client.post(import_url, data={'file': open(file_path, "rb")}).json()
        print_output("Importing test model:", resp)
        return resp["id"]


    def test_run(self):
        self.run_create_and_delete_tagger_group_removes_related_children_models_plots()
        self.run_create_tagger_group_training_and_task_signal()
        self.run_create_balanced_tagger_group_training_and_task_signal()
        self.run_tag_text(self.test_tagger_group_id)
        self.run_tag_doc()
        self.run_tag_random_doc()
        self.run_models_retrain()
        self.create_taggers_with_empty_fields()
        self.run_apply_tagger_group_to_index()
        self.run_apply_tagger_group_to_index_with_tag_limit()
        self.run_apply_tagger_group_to_index_invalid_input()
        self.run_model_export_import()
        self.run_tagger_instances_have_mention_to_tagger_group()


    def add_cleanup_files(self, tagger_id):
        tagger_object = Tagger.objects.get(pk=tagger_id)
        self.addCleanup(remove_file, tagger_object.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, tagger_object.plot.path)
        if tagger_object.embedding:
            self.addCleanup(remove_file, tagger_object.embedding.embedding_model.path)


    def tearDown(self) -> None:
        ec = ElasticCore()
        res = ec.delete_index(self.test_index_copy)
        ec.delete_index(index=self.test_index_name, ignore=[400, 404])
        print_output(f"Delete apply_taggers test index {self.test_index_copy}", res)


    def __cleanup_tagger_groups(self, created_tagger_group: TaggerGroup):
        for tagger in created_tagger_group.taggers.all():
            self.addCleanup(remove_file, tagger.model.path)
            self.addCleanup(remove_file, tagger.plot.path)
            # Check if not errors
            self.assertEqual(tagger.task.errors, '[]')
            # Check if Task gets created via a signal
            self.assertTrue(tagger.task is not None)
            # Check if Tagger gets trained and completed
            self.assertEqual(tagger.task.status, Task.STATUS_COMPLETED)
            self.add_cleanup_files(tagger.id)


    def __train_embedding_for_tagger(self) -> int:
        url = reverse(f"{VERSION_NAMESPACE}:embedding-list", kwargs={"project_pk": self.project.pk})
        payload = {
            "description": "TestEmbedding",
            "fields": [TEST_FIELD],
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("__train_embedding_for_tagger:response.data", response.data)
        return response.data["id"]


    def test_training_taggergroup_with_embedding(self):
        url = reverse(f"{VERSION_NAMESPACE}:tagger_group-list", kwargs={"project_pk": self.project.pk})
        embedding_id = self.__train_embedding_for_tagger()
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                "embedding": embedding_id
            }
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("test_training_taggergroup_with_embedding:response.data", response.data)
        created_tagger_group = TaggerGroup.objects.get(pk=response.data["id"])
        self.run_tag_text(created_tagger_group.pk)


    def run_create_tagger_group_training_and_task_signal(self):
        """Tests the endpoint for a new Tagger Group, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                "indices": [{"name": self.test_index_name}],
                "stop_words": ["asdfghjkl"]
            }
        }
        response = self.client.post(self.url, payload, format='json')
        # Check if TaggerGroup gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        print_output('test_create_tagger_group_training_and_task_signal:response.data', response.data)
        # add tagger to be tested
        created_tagger_group = TaggerGroup.objects.get(id=response.data['id'])
        self.test_tagger_group_id = created_tagger_group.pk
        self.__cleanup_tagger_groups(created_tagger_group)


    def run_create_balanced_tagger_group_training_and_task_signal(self):
        """Tests the endpoint for a new balanced Tagger Group, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                "indices": [{"name": self.test_index_name}],
                "stop_words": ["asdfghjkl"],
                "balanced": True
            }
        }
        response = self.client.post(self.url, payload, format='json')
        # Check if TaggerGroup gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        print_output('test_create_balanced_tagger_group_training_and_task_signal:response.data', response.data)
        # add tagger to be tested
        created_tagger_group = TaggerGroup.objects.get(id=response.data['id'])
        self.__cleanup_tagger_groups(created_tagger_group)


    def create_taggers_with_empty_fields(self):
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": [],
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                "indices": [{"name": self.test_index_name}]
            }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('create_taggers_with_empty_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_tag_text(self, tagger_group_id: int):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "see on mingi suvaline naisteka kommentaar. ehk joppab ja saab täägi", "n_similar_docs": 20, "n_candidate_tags": 20}
        tag_text_url = f'{self.url}{tagger_group_id}/tag_text/'
        response = self.client.post(tag_text_url, payload)
        print_output('test_tag_text_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, list))


    def run_tag_doc(self):
        """Tests the endpoint for the tag_doc action"""
        payload = {
            "doc": json.dumps({TEST_FIELD: "This is some test text for the Tagger Test"}),
            "n_similar_docs": 20,
            "n_candidate_tags": 20,
        }
        url = f'{self.url}{self.test_tagger_group_id}/tag_doc/'
        response = self.client.post(url, payload)
        print_output('test_tag_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, list))


    def run_tag_random_doc(self):
        """Tests the endpoint for the tag_random_doc action"""
        payload = {
            "indices": [{"name": self.test_index_name}]
        }
        url = f'{self.url}{self.test_tagger_group_id}/tag_random_doc/'
        response = self.client.post(url, format="json", data=payload)
        print_output('test_tag_random_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is list
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('tags' in response.data)


    def run_models_retrain(self):
        """Tests the endpoint for the models_retrain action"""
        url = f'{self.url}{self.test_tagger_group_id}/models_retrain/'
        response = self.client.post(url)
        print_output('test_models_retrain:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data
        self.assertTrue(response.data)
        self.assertTrue('success' in response.data)
        # remove retrained tagger models
        retrained_tagger_group = TaggerGroup.objects.get(id=response.data['tagger_group_id'])


    def run_apply_tagger_group_to_index(self):
        """Tests applying tagger group to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_group_to_index: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        url = f'{self.url}{self.test_imported_tagger_group_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "indices": [{"name": self.test_index_copy}],
            "fields": [TEST_FIELD],
            "lemmatize": False,
            "n_similar_docs": 10,
            "n_candidate_tags": 10
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_group_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_group_object = TaggerGroup.objects.get(pk=self.test_imported_tagger_group_id)

        # Wait til the task has finished
        while tagger_group_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_group_to_index: waiting for applying tagger task to finish, current status:', tagger_group_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_tagger_group_to_index:elastic aggerator results:", results)

        # Check if at least one new fact is added
        self.assertTrue(len(results) >= 1)

        # clean
        imported_tagger_group = TaggerGroup.objects.get(id=self.test_imported_tagger_group_id)

        for tagger in imported_tagger_group.taggers.all():
            # Remove tagger files after test is done
            self.add_cleanup_files(tagger.id)


    def run_apply_tagger_group_to_index_with_tag_limit(self):
        """Tests applying tagger group with tag limit to index using apply_to_index endpoint."""
        # Make sure reindexer task has finished
        while self.reindexer_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_group_to_index_tag_limit: waiting for reindexer task to finish, current status:', self.reindexer_object.task.status)
            sleep(2)

        url = f'{self.url}{self.test_imported_tagger_group_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name_tag_limit,
            "indices": [{"name": self.test_index_copy}],
            "fields": [TEST_FIELD],
            "lemmatize": False,
            "n_similar_docs": 10,
            "n_candidate_tags": 10,
            "max_tags": 1
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_group_to_index_tag_limit:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_group_object = TaggerGroup.objects.get(pk=self.test_imported_tagger_group_id)

        # Wait til the task has finished
        while tagger_group_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_group_to_index_tag_limit: waiting for applying tagger task to finish, current status:', tagger_group_object.task.status)
            sleep(2)

        # Scroll over the index to check if the correct amount of tags were added
        s = ElasticSearcher(indices=[self.test_index_copy], output=ElasticSearcher.OUT_RAW)

        for scroll_batch in s:
            for raw_doc in scroll_batch:
                hit = raw_doc["_source"]
                texta_facts = hit.get("texta_facts", [])
                relevant_facts = [fact for fact in texta_facts if fact["fact"] == self.new_fact_name_tag_limit]

                # Check if at most `max_tags` were added
                self.assertTrue(len(relevant_facts) <= 1)

        # clean
        imported_tagger_group = TaggerGroup.objects.get(id=self.test_imported_tagger_group_id)

        for tagger in imported_tagger_group.taggers.all():
            # Remove tagger files after test is done
            self.add_cleanup_files(tagger.id)


    def run_apply_tagger_group_to_index_invalid_input(self):
        """Tests applying tagger group to index with invalid input using apply_to_index endpoint."""

        url = f'{self.url}{self.test_tagger_group_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "indices": [{"name": self.test_index_copy}],
            "fields": "invalid_field_format",
            "lemmatize": False,
            "bulk_size": 50,
            "n_similar_docs": 10,
            "n_candidate_tags": 10
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_group_to_index_invalid_input:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_create_and_delete_tagger_group_removes_related_children_models_plots(self):
        payload = {
            "description": "TestTaggerGroup",
            "minimum_sample_size": 50,
            "fact_name": TEST_FACT_NAME,
            "tagger": {
                "fields": TEST_FIELD_CHOICE,
                "vectorizer": "Hashing Vectorizer",
                "classifier": "LinearSVC",
                "feature_selector": "SVM Feature Selector",
                "maximum_sample_size": 500,
                "negative_multiplier": 1.0,
                "indices": [{"name": self.test_index_name}]
            }
        }

        # Create a tagger_group.
        create_response = self.client.post(self.url, payload, format='json')
        tagger_group_url = create_response.data["url"]
        tagger_group_id = create_response.data["id"]
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        tagger_group = TaggerGroup.objects.get(id=tagger_group_id)
        child_taggers = tagger_group.taggers.all()

        # Check if there are more than one Taggers created as expected.
        self.assertEqual(child_taggers.count() > 1, True)

        # Check if files were created.
        for tagger in child_taggers:
            has_plot_file = pathlib.Path(tagger.plot.path).exists()
            has_model_file = pathlib.Path(tagger.model.path).exists()
            self.assertEqual(has_model_file, True)
            self.assertEqual(has_plot_file, True)

        # Delete the TaggerGroup
        self.client.delete(tagger_group_url)

        # Because it has a ManyToMany with no CASCADE, check if the child Taggers are gone.
        tagger_ids = [tagger.id for tagger in child_taggers]
        tagger_count = Tagger.objects.filter(id__in=tagger_ids).count()
        self.assertEqual(tagger_count == 0, True)

        # Check whether the files are deleted.
        for tagger in child_taggers:
            has_plot_file = pathlib.Path(tagger.plot.path).exists()
            has_model_file = pathlib.Path(tagger.model.path).exists()
            self.assertEqual(has_model_file, False)
            self.assertEqual(has_plot_file, False)


    def run_model_export_import(self):
        """Tests endpoint for model export and import"""
        test_tagger_group_id = self.test_tagger_group_id

        # retrieve model zip
        url = f'{self.url}{test_tagger_group_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        tg = TaggerGroup.objects.get(pk=response.data["id"])

        self.assertTrue(tg.taggers.count() > 1)

        # Check if the models and plot files exist.
        resources = tg.get_resource_paths()
        for item in resources:
            for path in item.values():
                file = pathlib.Path(path)
                self.assertTrue(file.exists())

        # Tests the endpoint for the tag_random_doc action"""
        url = f'{self.url}{tg.pk}/tag_random_doc/'
        response = self.client.post(url, format="json", data={"indices": [{"name": self.test_index_name}]})
        print_output('test_tag_random_doc_group:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(isinstance(response.data, dict))
        self.assertTrue('tags' in response.data)

        for tagger in tg.taggers.all():
            self.add_cleanup_files(tagger.id)


    def run_tagger_instances_have_mention_to_tagger_group(self):
        tg = TaggerGroup.objects.get(pk=self.test_tagger_group_id)
        description = tg.description

        for tagger in tg.taggers.all():
            tagger_url = reverse(f"{VERSION_NAMESPACE}:tagger-detail", kwargs={"project_pk": self.project.pk, "pk": tagger.pk})
            response = self.client.get(tagger_url)
            self.assertTrue(response.status_code == status.HTTP_200_OK)
            self.assertTrue("description" in response.data["tagger_groups"][0])
            self.assertTrue("id" in response.data["tagger_groups"][0])
            self.assertTrue("fact_name" in response.data["tagger_groups"][0])
            self.assertTrue(tg.description == response.data["tagger_groups"][0]["description"])
            self.assertTrue(tg.pk ==  response.data["tagger_groups"][0]["id"])
            self.assertTrue(tg.fact_name == response.data["tagger_groups"][0]["fact_name"])
            self.add_cleanup_files(tagger.id)
