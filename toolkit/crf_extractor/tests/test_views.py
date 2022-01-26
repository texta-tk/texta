import pathlib
from time import sleep
from io import BytesIO
import json

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from texta_elastic.searcher import EMPTY_QUERY
from toolkit.core.task.models import Task
from toolkit.helper_functions import reindex_test_dataset
from toolkit.crf_extractor.models import CRFExtractor
from toolkit.test_settings import (
    CRF_TEST_FIELD,
    TEST_KEEP_PLOT_FILES,
    TEST_VERSION_PREFIX,
    CRF_TEST_INDEX,
    TEST_INDEX
)
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.tools.utils_for_tests import (
    create_test_user,
    print_output,
    project_creation,
    remove_file
)


@override_settings(CELERY_ALWAYS_EAGER=True)
class CRFExtractorViewTests(APITransactionTestCase):
    """
    Tests CRF Extractor.
    """
    def setUp(self):
        self.test_incorrect_index_name = TEST_INDEX
        self.test_index_name = CRF_TEST_INDEX
        self.test_index_copy = reindex_test_dataset(from_index=CRF_TEST_INDEX)
        self.user = create_test_user('crfOwner', 'my@email.com', 'pw')
        self.project = project_creation("crfTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)
        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/crf_extractors/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'

        self.embedding_ids = [None]
        self.test_crf_ids = []
        self.client.login(username='crfOwner', password='pw')


    def tearDown(self) -> None:
        CRFExtractor.objects.all().delete()
        ec = ElasticCore()
        ec.delete_index(self.test_index_copy)


    def __train_embedding_for_test(self) -> int:
        url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        payload = {
            "description": "TestEmbedding",
            "fields": ["text_mlp.lemmas"],
            "max_vocab": 10000,
            "min_freq": 1,
            "num_dimensions": 100
        }
        response = self.client.post(url, data=payload, format="json")
        self.assertTrue(response.status_code == status.HTTP_201_CREATED)
        print_output("__train_embedding_for_test:response.data", response.data)

        return response.data["id"]


    def add_cleanup_files(self, id):
        crf = CRFExtractor.objects.get(pk=id)
        self.addCleanup(remove_file, crf.model.path)
        if not TEST_KEEP_PLOT_FILES:
            self.addCleanup(remove_file, crf.plot.path)
        if crf.embedding:
            self.addCleanup(remove_file, crf.embedding.embedding_model.path)


    def test_run(self):
        self.embedding_ids.append(self.__train_embedding_for_test())
        self.run_create_crf_training_and_task_signal()
        self.run_list_features()
        self.run_tag_text()
        self.run_test_export_import()
        self.run_apply_crf_to_index()

    def run_create_crf_training_and_task_signal(self):
        for embedding_id in self.embedding_ids:
            payload = {
                    "description": "TestCRF",
                    "test_size": 0.2,
                    "suffix_len": [2,3],
                    "c_values": [0.01, 0.1],
                    "query": json.dumps(EMPTY_QUERY),
                    "feature_fields": ["lemmas", "text"],
                    "context_feature_fields": ["lemmas", "text"],
                    "labels": ["GPE", "ORG", "PER"],
                    "mlp_field": CRF_TEST_FIELD,
                    "indices": [{"name": self.test_index_name}],
                    "embedding": embedding_id
            }
            response = self.client.post(self.url, payload, format='json')
            print_output('test_create_tagger_training_and_task_signal:response.data', response.data)

            # Check if Extractor gets created
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            created = CRFExtractor.objects.get(id=response.data['id'])
            # add to be tested
            self.test_crf_ids.append(created.pk)
            # Check if not errors
            self.assertEqual(created.task.errors, '[]')
            # Remove tagger files after test is done
            self.add_cleanup_files(created.id)
            # Check if Task gets created via a signal
            self.assertTrue(created.task is not None)
            # Check if gets trained and completed
            self.assertEqual(created.task.status, Task.STATUS_COMPLETED)


    def run_list_features(self):
        for test_tagger_id in self.test_crf_ids:
            url = f'{self.url}{test_tagger_id}/list_features/'
            response = self.client.get(url)
            print_output('test_list_features:response.data', response.data)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue(len(response.data["features"]["positive"]))
            self.assertTrue(len(response.data["features"]["negative"]))   


    def run_tag_text(self):
        """Tests the endpoint for the tag_text action"""
        payload = {"text": "New York is a place in the US."}

        for test_tagger_id in self.test_crf_ids:
            tag_text_url = f'{self.url}{test_tagger_id}/tag_text/'
            response = self.client.post(tag_text_url, payload)
            print_output('test_tag_text:response.data', response.data)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # Check if response data is not empty, but a result instead
            self.assertTrue(response.data)
            self.assertTrue(response.data["texta_facts"])


    def run_test_export_import(self):
        """Tests endpoint for model export and import"""
        test_model_id = self.test_crf_ids[0]

        # retrieve model zip
        url = f'{self.url}{test_model_id}/export_model/'
        response = self.client.get(url)

        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        imported_tagger_id = response.data['id']

        tagger = CRFExtractor.objects.get(id=imported_tagger_id)
        tagger_model_dir = pathlib.Path(RELATIVE_MODELS_PATH) / "crf"
        tagger_model_path = pathlib.Path(tagger.model.name)
        self.assertTrue(tagger_model_path.exists())

        # Check whether the model was saved into the right location.
        self.assertTrue(str(tagger_model_dir) in str(tagger.model.path))

        #self.run_tag_text([imported_tagger_id])
        self.add_cleanup_files(test_model_id)
        self.add_cleanup_files(imported_tagger_id)


    def run_apply_crf_to_index(self):
        """Tests applying extractor to index using apply_to_index endpoint."""
        test_tagger_id = self.test_crf_ids[0]
        url = f'{self.url}{test_tagger_id}/apply_to_index/'
        payload = {
            "description": "apply crf test task",
            "mlp_fields": ["text_mlp"],
            "indices": [{"name": self.test_index_copy}],
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_crf_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = CRFExtractor.objects.get(pk=test_tagger_id)

        # Wait til the task has finished
        while tagger_object.task.status != Task.STATUS_COMPLETED:
            print_output('test_apply_crf_to_index: waiting for applying tagger task to finish, current status:', tagger_object.task.status)
            sleep(2)

        results_old = ElasticAggregator(indices=[self.test_index_name]).get_fact_values_distribution("GPE")
        print_output("test_apply_crf_to_index_bofore:elastic aggerator results:", results_old)

        results_new = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution("GPE")
        print_output("test_apply_crf_to_index_after:elastic aggerator results:", results_new)

        # assert we have more facts than before
        for item in ["China", "U.S.", "Iran"]:
            self.assertTrue(results_old[item] < results_new[item])


# TODO: test training with incorrect fields & labels

# TODO: tests for retraining the model.

# TODO: test for incorrect MLP field.