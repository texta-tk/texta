import json
import os
import pathlib
from io import BytesIO

from django.test import TransactionTestCase, override_settings
from rest_framework import status

from toolkit.core.task.models import Task
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.embedding.models import Embedding
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.test_settings import TEST_FIELD_CHOICE, TEST_INDEX, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class EmbeddingViewTests(TransactionTestCase):

    def setUp(self):
        self.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')
        self.project = project_creation("embeddingTestProject", TEST_INDEX, self.user)
        self.project.users.add(self.user)

        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.test_embedding_id = None
        self.client.login(username='embeddingOwner', password='pw')


    def test_run(self):
        self.run_create_embedding_training_and_task_signal()
        self.run_predict(self.test_embedding_id)
        self.run_predict_with_negatives()
        self.run_phrase()
        self.run_model_export_import()
        self.create_embedding_with_empty_fields()
        self.create_embedding_then_delete_embedding_and_created_model()


    def tearDown(self):
        Embedding.objects.all().delete()


    def run_create_embedding_training_and_task_signal(self):
        """Tests the endpoint for a new Embedding, and if a new Task gets created via the signal"""
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100
        }

        response = self.client.post(self.url, json.dumps(payload), content_type='application/json')
        print_output('test_create_embedding_training_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_embedding_id = created_embedding.id
        # Remove Embedding files after test is done
        print_output("created embedding task status", created_embedding.task.status)
        # Check if Task gets created via a signal
        self.assertTrue(created_embedding.task is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(created_embedding.task.status, Task.STATUS_COMPLETED)


    def create_embedding_then_delete_embedding_and_created_model(self):
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        create_response = self.client.post(self.url, json.dumps(payload), content_type='application/json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        created_embedding_id = create_response.data['id']
        created_embedding_url = f'{self.url}{created_embedding_id}/'
        created_embedding_obj = Embedding.objects.get(id=created_embedding_id)
        embedding_model_location = created_embedding_obj.embedding_model.path
        self.assertEqual(os.path.isfile(embedding_model_location), True)

        additional_path = pathlib.Path(embedding_model_location + ".trainables.syn1neg.npy")
        additional_path_2 = pathlib.Path(embedding_model_location + ".wv.vectors.npy")
        additional_path.touch()
        additional_path_2.touch()

        delete_response = self.client.delete(created_embedding_url, content_type='application/json')
        print_output('delete_response.data: ', delete_response.data)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(os.path.isfile(embedding_model_location), False)

        print_output('delete_additional_embedding_files: ', not additional_path.exists())
        self.assertFalse(additional_path.exists())
        self.assertFalse(additional_path_2.exists())


    def create_embedding_with_empty_fields(self):
        """ tests to_repr serializer constant. Should fail because empty fields obj is filtered out in view"""
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": [],
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        create_response = self.client.post(self.url, json.dumps(payload), content_type='application/json')
        print_output("empty_fields_response", create_response.data)
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_predict(self, test_embedding_id):
        """Tests the endpoint for the predict action"""
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = {"positives": ["eesti", "läti"]}
        predict_url = f'{self.url}{test_embedding_id}/predict_similar/'
        response = self.client.post(predict_url, json.dumps(payload), content_type='application/json')
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_predict_with_negatives(self):
        """Tests the endpoint for the predict action"""
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = {"positives": ["eesti", "läti"], "negatives": ["juhtuma"]}
        predict_url = f'{self.url}{self.test_embedding_id}/predict_similar/'
        response = self.client.post(predict_url, json.dumps(payload), content_type='application/json')
        print_output('predict_with_negatives:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_phrase(self):
        """Tests the endpoint for the predict action"""
        payload = {"text": "See on mingi eesti keelne tekst testimiseks"}
        predict_url = f'{self.url}{self.test_embedding_id}/phrase_text/'
        response = self.client.post(predict_url, json.dumps(payload), content_type='application/json')
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_model_export_import(self):
        """Tests endpoint for model export and import"""
        # Retrieve model zip
        url = f'{self.url}{self.test_embedding_id}/export_model/'
        response = self.client.get(url)
        # Post model zip
        import_url = f'{self.url}import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', import_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Test prediction with imported embedding
        imported_embedding_id = response.data['id']
        print_output('test_import_model:response.data', response.data)
        embedding = Embedding.objects.get(id=imported_embedding_id)

        embedding_model_dir = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding"
        embedding_model_path = pathlib.Path(embedding.embedding_model.name)
        self.assertTrue(embedding_model_path.exists())
        # Check whether the model was saved into the right location.
        self.assertTrue(str(embedding_model_dir) in str(embedding.embedding_model.path))
        self.run_predict(imported_embedding_id)


    def run_embedding_training_with_specified_index_name(self):
        """
        Since index management got rewritten, it's necessary to separately test
        if the field is handled correctly.
        """
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
            "indices": [{"name": TEST_INDEX}]
        }

        response = self.client.post(self.url, json.dumps(payload), content_type='application/json')
        print_output("run_embedding_training_with_specified_index_name:response.data", response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_embedding_id = created_embedding.id
        # Remove Embedding files after test is done
        print_output("created embedding", created_embedding.task.status)
