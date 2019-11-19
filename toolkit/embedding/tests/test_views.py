from io import BytesIO
import json
import os
from django.db.models import signals

from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework.test import APIClient

from toolkit.test_settings import TEST_FIELD, TEST_INDEX, TEST_FIELD_CHOICE
from toolkit.core.project.models import Project
from toolkit.embedding.models import Embedding, EmbeddingCluster
from toolkit.core.task.models import Task
from toolkit.tools.utils_for_tests import create_test_user, print_output, remove_file
from toolkit.elastic.searcher import EMPTY_QUERY


class EmbeddingViewTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        # Owner of the project
        cls.user = create_test_user('embeddingOwner', 'my@email.com', 'pw')

        cls.project = Project.objects.create(
            title='embeddingTestProject',
            owner=cls.user,
            indices=TEST_INDEX
        )

        cls.url = f'/projects/{cls.project.id}/embeddings/'
        cls.project_url = f'/projects/{cls.project.id}'
        cls.cluster_url = f'/projects/{cls.project.id}/embedding_clusters/'

        # cls.user.profile.activate_project(cls.project)

        cls.test_embedding_id = None
        cls.test_embedding_clustering_id = None

    def setUp(self):
        self.client.login(username='embeddingOwner', password='pw')

    def test_run(self):
        self.run_create_embedding_training_and_task_signal()
        self.run_predict(self.test_embedding_id)
        self.run_predict_with_negatives()
        self.run_phrase()
        self.run_create_embedding_cluster_training_and_task_signal()
        self.run_embedding_cluster_browse()
        self.run_embedding_cluster_find_word()
        self.run_embedding_cluster_text()
        self.run_model_export_import()
        self.create_embedding_then_delete_embedding_and_created_model()
        self.run_patch_on_embedding_instances(self.test_embedding_id)
        self.run_put_on_embedding_instances(self.test_embedding_id)
        self.create_embedding_with_empty_fields()


    def run_create_embedding_training_and_task_signal(self):
        '''Tests the endpoint for a new Embedding, and if a new Task gets created via the signal'''
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }

        response = self.client.post(self.url, payload, format='json')
        print_output('test_create_embedding_training_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding = Embedding.objects.get(id=response.data['id'])
        self.test_embedding_id = created_embedding.id
        # Remove Embedding files after test is done
        print_output("created embedding task status", created_embedding.task.status)
        self.addCleanup(remove_file, json.loads(created_embedding.location)['embedding'])
        self.addCleanup(remove_file, json.loads(created_embedding.location)['phraser'])
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
        create_response = self.client.post(self.url, payload, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        created_embedding_id = create_response.data['id']
        created_embedding_url = f'{self.url}{created_embedding_id}/'
        created_embedding_obj = Embedding.objects.get(id=created_embedding_id)
        embedding_model_location = json.loads(created_embedding_obj.location)['embedding']
        phraser_model_location = json.loads(created_embedding_obj.location)['phraser']

        delete_response = self.client.delete(created_embedding_url, format='json')
        print_output('delete_response.data: ', delete_response.data)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        assert not os.path.isfile(embedding_model_location)
        assert not os.path.isfile(phraser_model_location)

    def run_patch_on_embedding_instances(self, test_embedding_id):
        ''' Tests patch response success for Tagger fields '''
        payload = {
            "description": "PatchedEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        embedding_url = f'{self.url}{test_embedding_id}/'
        patch_response = self.client.patch(embedding_url, payload, format='json')
        print_output("patch_response", patch_response.data)
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

    def run_put_on_embedding_instances(self, test_embedding_id):
        ''' Tests put response success for Tagger fields '''
        payload = {
            "description": "PutEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": TEST_FIELD_CHOICE,
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        embedding_url = f'{self.url}{test_embedding_id}/'
        # get_response = self.client.get(tagger_url, format='json')
        put_response = self.client.put(embedding_url, payload, format='json')
        print_output("put_response", put_response.data)
        self.assertEqual(put_response.status_code, status.HTTP_200_OK)


    def create_embedding_with_empty_fields(self):
        ''' tests to_repr serializer constant. Should fail because empty fields obj is filtered out in view'''
        payload = {
            "description": "TestEmbedding",
            "query": json.dumps(EMPTY_QUERY),
            "fields": [],
            "max_vocab": 10000,
            "min_freq": 5,
            "num_dimensions": 100,
        }
        create_response = self.client.post(self.url, payload, format='json')
        print_output("empty_fields_response", create_response.data)
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)


    def run_predict(self, test_embedding_id):
        '''Tests the endpoint for the predict action'''
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = { "positives": ["eesti", "läti"] }
        predict_url = f'{self.url}{test_embedding_id}/predict_similar/'
        response = self.client.post(predict_url, payload)
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)

    def run_predict_with_negatives(self):
        '''Tests the endpoint for the predict action'''
        # Send only "text" in payload, because "output_size" should be 10 by default
        payload = { "positives": ["eesti", "läti"], "negatives": ["juhtuma"] }
        predict_url = f'{self.url}{self.test_embedding_id}/predict_similar/'
        response = self.client.post(predict_url, payload)
        print_output('predict_with_negatives:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)

    def run_phrase(self):
        '''Tests the endpoint for the predict action'''
        payload = { "text": "See on mingi eesti keelne tekst testimiseks" }
        predict_url = f'{self.url}{self.test_embedding_id}/phrase_text/'
        response = self.client.post(predict_url, payload)
        print_output('predict:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)


    def run_create_embedding_cluster_training_and_task_signal(self):
        '''Tests the endpoint for a new EmbeddingCluster, and if a new Task gets created via the signal'''
        payload = {
            "embedding": self.test_embedding_id,
            "num_clusters": 10
        }

        response = self.client.post(self.cluster_url, payload)
        print_output('test_create_embedding_clustering_and_task_signal:response.data', response.data)
        # Check if Embedding gets created
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_embedding_cluster = EmbeddingCluster.objects.get(id=response.data['id'])
        self.test_embedding_clustering_id = created_embedding_cluster.id
        # Check if not errors
        self.assertEqual(created_embedding_cluster.task.errors, '')
        # Check if Task gets created via a signal
        self.assertTrue(created_embedding_cluster.task is not None)
        # Check if Embedding gets trained and completed
        self.assertEqual(created_embedding_cluster.task.status, Task.STATUS_COMPLETED)
        # remove created embedding cluster model
        self.addCleanup(remove_file, json.loads(created_embedding_cluster.location)['cluster'])

    def run_embedding_cluster_browse(self):
        '''Tests the endpoint for the browse action'''
        payload = { "number_of_clusters": 10, "cluster_order": True }
        browse_url = f'{self.cluster_url}{self.test_embedding_clustering_id}/browse_clusters/'
        response = self.client.post(browse_url, payload)
        print_output('browse:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)

    def run_embedding_cluster_find_word(self):
        '''Tests the endpoint for the find_word action'''
        payload = { "text": "putin" }
        browse_url = f'{self.cluster_url}{self.test_embedding_clustering_id}/find_cluster_by_word/'
        response = self.client.post(browse_url, payload)
        print_output('find_word:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)

    def run_embedding_cluster_text(self):
        '''Tests the endpoint for the find_word action'''
        payload = {"text": "putin ja teised reptiloidid nagu ansip ja kallas. nats ja nats"}
        browse_url = f'{self.cluster_url}{self.test_embedding_clustering_id}/cluster_text/'
        response = self.client.post(browse_url, payload)
        print_output('cluster_text:response.data', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response data is not empty, but a result instead
        self.assertTrue(response.data)

    def run_model_export_import(self):
        '''Tests endpoint for model export and import'''
        # retrieve model zip
        url = f'{self.url}{self.test_embedding_id}/export_model/'
        response = self.client.get(url)
        # post model zip
        import_url = f'{self.project_url}/import_model/'
        response = self.client.post(import_url, data={'file': BytesIO(response.content)})
        print_output('test_import_model:response.data', response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Test prediction with imported embedding
        imported_embedding_id = response.data['id']
        self.run_predict(imported_embedding_id)

        # remove embedding and phraser models
        created_embedding = Embedding.objects.get(id=imported_embedding_id)
        created_embedding_location = json.loads(created_embedding.location)['embedding']
        created_phraser_location = json.loads(created_embedding.location)['phraser']

        self.addCleanup(remove_file, created_embedding_location)
        self.addCleanup(remove_file, created_phraser_location)
