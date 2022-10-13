import json
import pathlib
from io import BytesIO

from django.test import TransactionTestCase, override_settings
from rest_framework import status

from toolkit.core.task.models import Task
from texta_elastic.core import ElasticCore
from texta_elastic.searcher import EMPTY_QUERY
from toolkit.embedding.models import Embedding
from toolkit.helper_functions import reindex_test_dataset
from toolkit.settings import RELATIVE_MODELS_PATH
from toolkit.test_settings import TEST_FIELD_CHOICE, TEST_VERSION_PREFIX
from toolkit.tools.utils_for_tests import create_test_user, print_output, project_creation


@override_settings(CELERY_ALWAYS_EAGER=True)
class EmbeddingViewSnowballTests(TransactionTestCase):

    def setUp(self):
        self.test_index_name = reindex_test_dataset()
        self.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')
        self.project = project_creation("embeddingTestProject", self.test_index_name, self.user)
        self.project.users.add(self.user)

        self.url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}/embeddings/'
        self.project_url = f'{TEST_VERSION_PREFIX}/projects/{self.project.id}'
        self.test_embedding_id = None
        self.client.login(username='embeddingOwner', password='pw')


    def test_run(self):
        self.run_create_default_embedding_training_and_task_signal()
        self.run_predict(self.test_embedding_id)
        self.run_phrase()
        self.run_model_export_import()


    def tearDown(self):
        ElasticCore().delete_index(index=self.test_index_name, ignore=[400, 404])
        Embedding.objects.all().delete()


    def run_create_default_embedding_training_and_task_signal(self):
        """Tests the endpoint for a new Embedding by default (embedding_type == "W2VEmbedding"), and if a new Task gets created via the signal"""
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "snowball_language": "estonian",
            "max_vocab": 1000,
            "min_freq": 5,
            "num_dimensions": 100
        }

        response = self.client.post(self.url, json.dumps(payload), content_type='application/json')
        print_output('test_create_default_embedding_training_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_embedding_id = created_embedding.id
        # Remove Embedding files after test is done
        task_object = created_embedding.tasks.last()
        print_output("created default embedding task status", task_object.status)
        # Check if Task gets created via a signal
        self.assertTrue(task_object is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(task_object.status, Task.STATUS_COMPLETED)
        self.assertTrue(task_object.progress <= 100)


    def run_predict(self, test_embedding_id):
        """Tests the endpoint for the predict action"""
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = {"positives_used": ["eesti", "läti"]}
        predict_url = f'{self.url}{test_embedding_id}/predict_similar/'
        response = self.client.post(predict_url, json.dumps(payload), content_type='application/json')
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_phrase(self):
        """Tests the endpoint for the predict action"""
        payload = {"text": "See on mingi eesti keelne tekst testimiseks"}
        predict_url = f'{self.url}{self.test_embedding_id}/phrase_text/'
        response = self.client.post(predict_url, json.dumps(payload), content_type='application/json')
        print_output('predict_phrase:response.data', response.data)
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
