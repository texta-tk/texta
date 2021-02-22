import json
import pathlib
import uuid
from io import BytesIO

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from toolkit.elastic.aggregator import ElasticAggregator
from toolkit.elastic.core import ElasticCore
from toolkit.elastic.models import Reindexer
from toolkit.core.task.models import Task
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.test_settings import (TEST_FACT_NAME,
                                   TEST_FIELD,
                                   TEST_FIELD_CHOICE,
                                   TEST_INDEX,
                                   TEST_QUERY,
                                   TEST_VERSION_PREFIX,
                                   TEST_KEEP_PLOT_FILES, VERSION_NAMESPACE)
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation, remove_file


@override_settings(CELERY_ALWAYS_EAGER=True)
class TaggerGroupViewTests(APITransactionTestCase):

    def setUp(self):
        # Owner of the project
        self.user = create_test_user('taggerOwner', 'my@email.com', 'pw')
        self.project = project_creation("taggerGroupTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/tagger_groups/'
        self.test_tagger_group_id = None

        self.client.login(username='taggerOwner', password='pw')
        # new fact name and value used when applying tagger to index
        self.new_fact_name = "TEST_TAGGER_GROUP_NAME"

        # Create copy of test index
        self.reindex_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/reindexer/'
        # Generate name for new index containing random id to make sure it doesn't already exist
        self.test_index_copy = f"test_apply_tagger_group_{uuid.uuid4().hex}"

        self.reindex_payload = {
            "description": "test index for applying tagger group",
            "indices": [TEST_INDEX],
            "new_index": self.test_index_copy,
            "fields": [TEST_FIELD]
        }
        resp = self.client.post(self.reindex_url, self.reindex_payload, format='json')
        print_output("reindex test index for applying tagger group:response.data:", resp.json())
        self.reindexer_object = Reindexer.objects.get(pk=resp.json()["id"])


    def test_run(self):
        self.run_create_and_delete_tagger_group_removes_related_children_models_plots()
        self.run_create_tagger_group_training_and_task_signal()
        self.run_tag_text()
        self.run_tag_doc()
        self.run_tag_random_doc()
        self.run_models_retrain()
        self.create_taggers_with_empty_fields()
        self.run_apply_tagger_group_to_index()
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
        res = ElasticCore().delete_index(self.test_index_copy)
        print_output(f"Delete apply_taggers test index {self.test_index_copy}", res)


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
                "negative_multiplier": 1.0
            }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_tagger_group_training_and_task_signal:response.data', response.data)
        # Check if TaggerGroup gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # add tagger to be tested
        created_tagger_group = TaggerGroup.objects.get(id=response.data['id'])
        self.test_tagger_group_id = created_tagger_group.pk

        for tagger in created_tagger_group.taggers.all():
            # run this for each tagger in tagger group
            # Remove tagger files after test is done
            self.addCleanup(remove_file, tagger.model.path)
            self.addCleanup(remove_file, tagger.plot.path)
            # Check if not errors
            self.assertEqual(tagger.task.errors, '[]')
            # Check if Task gets created via a signal
            self.assertTrue(tagger.task is not None)
            # Check if Tagger gets trained and completed
            self.assertEqual(tagger.task.status, Task.STATUS_COMPLETED)

            self.add_cleanup_files(tagger.id)


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
            }
        }
        response = self.client.post(self.url, payload, format='json')
        print_output('create_taggers_with_empty_fields:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_tag_text(self):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "see on mingi suvaline naisteka kommentaar. ehk joppab ja saab täägi", "n_similar_docs": 20, "n_candidate_tags": 20}
        tag_text_url = f'{self.url}{self.test_tagger_group_id}/tag_text/'
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
            "indices": [{"name": TEST_INDEX}]
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

        url = f'{self.url}{self.test_tagger_group_id}/apply_to_index/'

        payload = {
            "description": "apply tagger test task",
            "new_fact_name": self.new_fact_name,
            "indices": [{"name": self.test_index_copy}],
            "fields": [TEST_FIELD],
            "query": json.dumps(TEST_QUERY),
            "lemmatize": False,
            "bulk_size": 50,
            "n_similar_docs": 10,
            "n_candidate_tags": 10
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_tagger_group_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_group_object = TaggerGroup.objects.get(pk=self.test_tagger_group_id)

        # Wait til the task has finished
        while tagger_group_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_tagger_group_to_index: waiting for applying tagger task to finish, current status:', tagger_group_object.task.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(self.new_fact_name)
        print_output("test_apply_tagger_group_to_index:elastic aggerator results:", results)

        # Check if applying tagger group results in at least one new fact value for each tagger in the group
        # Exact numbers cannot be checked as creating taggers contains random and thus
        # predicting with them isn't entirely deterministic
        self.assertTrue(len(results) >= 1)


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
        response = self.client.post(url, format="json", data={"indices": [{"name": TEST_INDEX}]})
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
            self.assertTrue(tg.description in response.data["tagger_groups"])
            self.add_cleanup_files(tagger.id)
