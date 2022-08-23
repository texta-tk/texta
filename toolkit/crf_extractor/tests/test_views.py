import json
import pathlib
from io import BytesIO
from time import sleep

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITransactionTestCase
from texta_elastic.aggregator import ElasticAggregator
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.task.models import Task
from toolkit.crf_extractor.models import CRFExtractor
from toolkit.helper_functions import reindex_test_dataset
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.test_settings import (CRF_TEST_FIELD, CRF_TEST_INDEX, TEST_INDEX, TEST_KEEP_PLOT_FILES, TEST_VERSION_PREFIX)
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
        self.run_apply_crf_to_index_with_specified_label_suffix()
        self.run_retraining_view_on_trained_crf_model()


    def run_create_crf_training_and_task_signal(self):
        for embedding_id in self.embedding_ids:
            payload = {
                "description": "TestCRF",
                "test_size": 0.2,
                "suffix_len": [2, 3],
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
            task_object = created.tasks.last()
            self.assertEqual(task_object.errors, '[]')
            # Remove tagger files after test is done
            self.add_cleanup_files(created.id)
            # Check if Task gets created via a signal
            self.assertTrue(task_object is not None)
            # Check if gets trained and completed
            self.assertEqual(task_object.status, Task.STATUS_COMPLETED)


    def run_list_features(self, tagger_id=None):
        taggers_to_test = self.test_crf_ids if tagger_id is None else [tagger_id]
        for test_tagger_id in taggers_to_test:
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

        # self.run_tag_text([imported_tagger_id])
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
        task_object = tagger_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_crf_to_index: waiting for applying tagger task to finish, current status:', task_object.status)
            sleep(2)

        results_old = ElasticAggregator(indices=[self.test_index_name]).get_fact_values_distribution("GPE")
        print_output("test_apply_crf_to_index_before:elastic aggerator results:", results_old)

        results_new = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution("GPE")
        print_output("test_apply_crf_to_index_after:elastic aggerator results:", results_new)

        # assert we have more facts than before
        for item in ["China", "Russia", "Iran"]:
            self.assertTrue(results_old[item] < results_new[item])


    def run_apply_crf_to_index_with_specified_label_suffix(self):
        """Tests applying extractor to index with specified label suffix using apply_to_index endpoint."""
        test_tagger_id = self.test_crf_ids[0]
        url = f'{self.url}{test_tagger_id}/apply_to_index/'
        label_suffix = "CRF_TEST"
        payload = {
            "description": "apply crf test task",
            "mlp_fields": ["text_mlp"],
            "indices": [{"name": self.test_index_copy}],
            "label_suffix": label_suffix
        }
        response = self.client.post(url, payload, format='json')
        print_output('test_apply_crf_to_index:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        tagger_object = CRFExtractor.objects.get(pk=test_tagger_id)

        # Wait til the task has finished
        task_object = tagger_object.tasks.last()
        while task_object.status != Task.STATUS_COMPLETED:
            print_output('test_apply_crf_to_index_with_specified_label_suffix: waiting for applying tagger task to finish, current status:', task_object.status)
            sleep(2)

        results = ElasticAggregator(indices=[self.test_index_copy]).get_fact_values_distribution(f"GPE_{label_suffix}")
        print_output("test_apply_crf_to_index_with_specified_label_suffix:elastic aggerator results:", results)

        # assert we have more facts than before
        self.assertTrue(len(results) > 1)


    def run_retraining_view_on_trained_crf_model(self):
        tagger_id = self.test_crf_ids[0]
        tagger_orm: CRFExtractor = CRFExtractor.objects.get(pk=tagger_id)
        model_path = pathlib.Path(tagger_orm.model.path)
        print_output('run_retraining_view_on_trained_crf_model:assert that previous model doesnt exist', data=model_path.exists())
        self.assertTrue(model_path.exists())

        url = reverse("v2:crf_extractor-retrain-extractor", kwargs={"project_pk": self.project.pk, "pk": tagger_id})
        response = self.client.post(url)
        print_output("run_retraining_view_on_trained_crf_model:response.data", response.data)
        self.assertTrue(response.status_code == status.HTTP_200_OK)
        self.run_list_features(tagger_id=tagger_id)

        # Ensure that previous tagger is deleted properly.
        print_output('run_retraining_view_on_trained_crf_model:assert that previous model doesnt exist', data=model_path.exists())
        self.assertFalse(model_path.exists())
        # Ensure that the freshly created model wasn't deleted.
        tagger_orm.refresh_from_db()
        self.assertNotEqual(tagger_orm.model.path, str(model_path))


# TODO: test training with incorrect fields & labels


# TODO: test for incorrect MLP field.
